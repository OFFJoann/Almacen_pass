from rest_framework import viewsets, permissions, status, decorators
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied
from rest_framework.authentication import TokenAuthentication
from rest_framework.response import Response
from django.db.models import Q
from django.utils import timezone
from django.urls import reverse
from datetime import timedelta
import secrets
from .models import PasswordEntry, PasswordHistory, Folder, Category, Tag, Vault, Share, SharedPassword
from .serializers import (
    PasswordEntrySerializer, PasswordEntryListSerializer,
    FolderSerializer, CategorySerializer, TagSerializer,
    ShareSerializer, VaultSerializer
)
from .encryption import generate_password, generate_passphrase, calculate_entropy


class PasswordEntryViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    authentication_classes = [TokenAuthentication]

    def get_queryset(self):
        vault, _ = Vault.objects.get_or_create(user=self.request.user)
        qs = PasswordEntry.objects.filter(vault=vault, is_deleted=False, is_obsolete=False)
        shared_ids = Share.objects.filter(
            Q(shared_with_user=self.request.user) | Q(shared_with_group__members=self.request.user),
            is_revoked=False,
            entry__is_deleted=False,
            entry__is_obsolete=False,
        ).filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())
        ).values_list('entry_id', flat=True).distinct()
        qs = qs | PasswordEntry.objects.filter(pk__in=shared_ids, is_deleted=False, is_obsolete=False)
        folder = self.request.query_params.get('folder')
        category = self.request.query_params.get('category')
        search = self.request.query_params.get('search')
        if folder:
            qs = qs.filter(folder_id=folder)
        if category:
            qs = qs.filter(category_id=category)
        if search:
            qs = qs.filter(name__icontains=search)
        return qs.distinct()

    def get_serializer_class(self):
        if self.action == 'list':
            return PasswordEntryListSerializer
        return PasswordEntrySerializer

    def perform_create(self, serializer):
        vault, _ = Vault.objects.get_or_create(user=self.request.user)
        entry = serializer.save(vault=vault)
        entry.set_username(self.request.data.get('username', ''))
        entry.set_password(self.request.data.get('password', ''))
        entry.set_notes(self.request.data.get('notes', ''))
        entry.save()

    def perform_update(self, serializer):
        if serializer.instance.vault.user_id != self.request.user.id:
            raise PermissionDenied('No tienes permiso para editar este registro compartido.')
        entry = serializer.save()
        data = self.request.data
        if 'username' in data:
            entry.set_username(data.get('username', ''))
        if 'password' in data:
            entry.set_password(data.get('password', ''))
        if 'notes' in data:
            entry.set_notes(data.get('notes', ''))
        entry.save()

    @action(detail=True, methods=['post'], url_path='verify_totp')
    def verify_totp(self, request, pk=None):
        import pyotp
        entry = self.get_object()
        if entry.vault.user_id != request.user.id:
            raise PermissionDenied('No tienes permiso para editar este registro compartido.')
        secret = (request.data.get('secret') or '').strip()
        code = (request.data.get('code') or '').strip()
        if not secret:
            return Response({'error': 'La clave secreta es obligatoria.'}, status=status.HTTP_400_BAD_REQUEST)
        if not code:
            return Response({'error': 'El código de verificación es obligatorio.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            totp = pyotp.TOTP(secret)
        except Exception:
            return Response({'error': 'La clave secreta no es válida.'}, status=status.HTTP_400_BAD_REQUEST)
        if not totp.verify(code, valid_window=1):
            return Response(
                {'error': 'El código no coincide. El 2FA no fue configurado.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        entry.set_totp_secret(secret)
        entry.version += 1
        entry.save(update_fields=['totp_secret_encrypted', 'totp_secret_nonce', 'totp_secret_salt', 'version'])
        PasswordHistory.objects.create(
            entry=entry,
            password_encrypted=entry.password_encrypted,
            password_nonce=entry.password_nonce,
            password_salt=entry.password_salt,
            changed_by=request.user,
            changes_summary='2FA verificado',
        )
        return Response({'ok': True, 'has_totp': entry.has_totp, 'totp': entry.get_current_totp()})

    @action(detail=True, methods=['post'], url_path='remove_totp')
    def remove_totp(self, request, pk=None):
        entry = self.get_object()
        if entry.vault.user_id != request.user.id:
            raise PermissionDenied('No tienes permiso para editar este registro compartido.')
        entry.set_totp_secret('')
        entry.version += 1
        entry.save(update_fields=['totp_secret_encrypted', 'totp_secret_nonce', 'totp_secret_salt', 'version'])
        PasswordHistory.objects.create(
            entry=entry,
            password_encrypted=entry.password_encrypted,
            password_nonce=entry.password_nonce,
            password_salt=entry.password_salt,
            changed_by=request.user,
            changes_summary='2FA eliminado',
        )
        return Response({'ok': True, 'has_totp': False, 'totp': ''})

    def perform_destroy(self, instance):
        if instance.vault.user_id != self.request.user.id:
            raise PermissionDenied('No tienes permiso para eliminar este registro compartido.')
        instance.delete()

    @action(detail=False, methods=['post'], url_path='check_duplicate')
    def check_duplicate(self, request):
        from urllib.parse import urlsplit
        url = (request.data.get('url') or '').strip()
        username = ((request.data.get('username') or '')).strip().lower()
        password = request.data.get('password') or ''
        if not url or not password:
            return Response({'duplicate': False})

        def norm(u):
            try:
                parts = urlsplit(u)
                return (parts.hostname or '').replace('www.', '').lower(), parts.path.rstrip('/').lower()
            except Exception:
                return u.lower(), ''

        want_host, want_path = norm(url)
        if not want_host:
            return Response({'duplicate': False})

        for entry in self.get_queryset().iterator():
            cur = (entry.url or '')
            if not cur:
                continue
            host, path = norm(cur)
            if not host:
                continue
            # Mismo origen + mismo camino (tolerante a www, barra final, query/fragmento)
            # o bien mismo hostname (mismo sitio) con las mismas credenciales.
            same_page = host == want_host and path == want_path
            same_site = host == want_host
            if not (same_page or same_site):
                continue
            if username and (entry.get_username() or '').strip().lower() != username:
                continue
            if entry.get_password() == password:
                return Response({'duplicate': True})
        return Response({'duplicate': False})


class FolderViewSet(viewsets.ModelViewSet):
    serializer_class = FolderSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Folder.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class CategoryViewSet(viewsets.ModelViewSet):
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Category.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class TagViewSet(viewsets.ModelViewSet):
    serializer_class = TagSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Tag.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_generate_password(request):
    length = int(request.query_params.get('length', 24))
    use_upper = request.query_params.get('upper', 'true').lower() == 'true'
    use_lower = request.query_params.get('lower', 'true').lower() == 'true'
    use_digits = request.query_params.get('digits', 'true').lower() == 'true'
    use_symbols = request.query_params.get('symbols', 'true').lower() == 'true'
    exclude_similar = request.query_params.get('exclude_similar', 'false').lower() == 'true'
    exclude_ambiguous = request.query_params.get('exclude_ambiguous', 'false').lower() == 'true'
    passphrase = request.query_params.get('passphrase', 'false').lower() == 'true'
    num_words = int(request.query_params.get('num_words', 4))

    if passphrase:
        password = generate_passphrase(num_words)
    else:
        password = generate_password(length, use_upper, use_lower, use_digits,
                                      use_symbols, exclude_similar, exclude_ambiguous)

    entropy = calculate_entropy(password)

    return Response({'password': password, 'entropy': entropy})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_share_password(request):
    """Crea una contraseña compartida por enlace público temporal (máx. 7 días)
    vía API (TokenAuthentication), igual que el modal de la web."""
    password = (request.data.get('password') or '').strip()
    if not password:
        return Response(
            {'status': 'error', 'message': 'Ingresa la contraseña que deseas compartir.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if len(password) > 4096:
        return Response(
            {'status': 'error', 'message': 'La contraseña es demasiado larga (máx. 4096 caracteres).'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        days = int(request.data.get('days') or '7')
    except (TypeError, ValueError):
        days = 7
    days = max(1, min(days, 7))

    max_uses_raw = str(request.data.get('max_uses') or '').strip()
    max_uses = 7
    if max_uses_raw:
        try:
            max_uses = int(max_uses_raw)
        except (TypeError, ValueError):
            max_uses = 7
        max_uses = max(1, min(max_uses, 7))

    share = SharedPassword.objects.create(
        token=secrets.token_urlsafe(32),
        created_by=request.user,
        days=days,
        max_uses=max_uses,
        expires_at=timezone.now() + timedelta(days=days),
    )
    share.set_password(password)
    share.save(update_fields=['password_encrypted', 'password_nonce', 'password_salt'])

    from apps.audit.models import AuditLog
    AuditLog.objects.create(
        user=request.user,
        action='PASSWORD_SHARED',
        details=f'Created public share for a pasted password ({days} days, max {max_uses} uses)',
        result='success',
        ip_address=request.META.get('REMOTE_ADDR', ''),
    )

    url = request.build_absolute_uri(reverse('public_link', kwargs={'token': share.token}))
    return Response({
        'status': 'ok',
        'url': url,
        'pk': str(share.pk),
        'days': days,
        'max_uses': max_uses,
        'expires_at': share.expires_at.strftime('%d/%m/%Y %H:%M'),
    })
