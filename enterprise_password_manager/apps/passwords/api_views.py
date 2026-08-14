from rest_framework import viewsets, permissions, status, decorators
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied
from rest_framework.authentication import TokenAuthentication
from rest_framework.response import Response
from django.db.models import Q
from django.utils import timezone
from .models import PasswordEntry, PasswordHistory, Folder, Category, Tag, Vault, Share
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
