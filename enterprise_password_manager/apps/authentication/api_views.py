from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.authentication import TokenAuthentication
from django.contrib.auth import authenticate, login, logout
from django.utils import timezone
from .utils import parse_user_agent, get_client_ip
from apps.users.models import LoginHistory, ActiveSession


@api_view(['POST'])
@permission_classes([AllowAny])
def api_login(request):
    email = request.data.get('email')
    password = request.data.get('password')
    user = authenticate(request, username=email, password=password)
    if user is not None:
        if user.mfa_enabled:
            return Response({'mfa_required': True, 'user_id': str(user.id)}, status=status.HTTP_200_OK)
        login(request, user)
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        parsed = parse_user_agent(user_agent)
        ip = get_client_ip(request)
        LoginHistory.objects.create(user=user, ip_address=ip, user_agent=user_agent,
                                     browser=parsed['browser'], os=parsed['os'], device=parsed['device'],
                                     success=True, session_key=request.session.session_key or '')
        ActiveSession.objects.update_or_create(
            user=user, session_key=request.session.session_key,
            defaults={'ip_address': ip, 'user_agent': user_agent, 'browser': parsed['browser'],
                      'os': parsed['os'], 'device': parsed['device'],
                      'expires_at': timezone.now() + timezone.timedelta(hours=1)}
        )
        return Response({'success': True, 'email': user.email})
    return Response({'error': 'Credenciales inválidas'}, status=status.HTTP_401_UNAUTHORIZED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_logout(request):
    logout(request)
    return Response({'success': True})


@api_view(['POST'])
@permission_classes([AllowAny])
def api_mfa_verify(request):
    from django.contrib.auth import get_user_model
    import pyotp
    User = get_user_model()
    user_id = request.data.get('user_id')
    code = request.data.get('code')
    try:
        user = User.objects.get(pk=user_id)
        totp = pyotp.TOTP(user.mfa_secret)
        if totp.verify(code):
            login(request, user)
            return Response({'success': True, 'email': user.email})
        return Response({'error': 'Código inválido'}, status=status.HTTP_401_UNAUTHORIZED)
    except User.DoesNotExist:
        return Response({'error': 'Usuario no encontrado'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_me(request):
    user = request.user
    return Response({
        'id': str(user.id),
        'email': user.email,
        'full_name': user.full_name,
        'is_staff': user.is_staff,
        'is_superuser': user.is_superuser,
        'mfa_enabled': user.mfa_enabled,
    })


@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def api_token_login(request):
    """Login para la extensión del navegador. Devuelve token si MFA no está activo."""
    email = (request.data.get('email') or '').strip().lower()
    password = request.data.get('password') or ''
    user = authenticate(request, username=email, password=password)
    if user is None:
        return Response({'error': 'Credenciales inválidas'}, status=status.HTTP_401_UNAUTHORIZED)
    if not user.is_active:
        return Response({'error': 'Usuario inactivo'}, status=status.HTTP_403_FORBIDDEN)
    if user.mfa_enabled:
        return Response({'mfa_required': True, 'user_id': str(user.id)}, status=status.HTTP_200_OK)
    token, _ = Token.objects.get_or_create(user=user)
    _log_extension_login(request, user)
    return Response({'token': token.key, 'email': user.email, 'full_name': user.full_name})


@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def api_token_mfa_verify(request):
    """Verifica el código TOTP y entrega el token (para usuarios con MFA)."""
    import pyotp
    from django.contrib.auth import get_user_model
    from .utils import parse_user_agent, get_client_ip
    from apps.users.models import LoginHistory, ActiveSession

    User = get_user_model()
    user_id = request.data.get('user_id')
    code = request.data.get('code')
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return Response({'error': 'Usuario no encontrado'}, status=status.HTTP_404_NOT_FOUND)
    totp = pyotp.TOTP(user.mfa_secret)
    if not totp.verify(code):
        return Response({'error': 'Código inválido'}, status=status.HTTP_401_UNAUTHORIZED)
    token, _ = Token.objects.get_or_create(user=user)
    _log_extension_login(request, user)
    return Response({'token': token.key, 'email': user.email, 'full_name': user.full_name})


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def api_token_logout(request):
    token = getattr(request.auth, 'delete', None)
    if callable(token):
        request.auth.delete()
    # Cierra también la sesión web con la que se generó el token, si existe.
    session_key = request.headers.get('X-Session-ID', '')
    if session_key:
        from importlib import import_module
        from django.conf import settings
        engine = import_module(settings.SESSION_ENGINE)
        store = engine.SessionStore(session_key)
        if store.get('_auth_user_id') == str(request.user.pk):
            store.delete()
            ActiveSession.objects.filter(user=request.user, session_key=session_key).delete()
            LoginHistory.objects.filter(
                user=request.user, session_key=session_key, logout_at__isnull=True
            ).update(logout_at=timezone.now())
    return Response({'success': True})


@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def api_token_from_session(request):
    """Convierte la sesión web activa (cookie de sesión) en un token API, para la extensión."""
    from importlib import import_module
    from django.conf import settings
    from django.contrib.auth import get_user_model

    session_key = request.headers.get('X-Session-ID', '')
    if not session_key:
        return Response({'error': 'Sesión no activa'}, status=status.HTTP_401_UNAUTHORIZED)
    engine = import_module(settings.SESSION_ENGINE)
    store = engine.SessionStore(session_key)
    user_id = store.get('_auth_user_id')
    if not user_id:
        return Response({'error': 'Sesión no válida'}, status=status.HTTP_401_UNAUTHORIZED)
    try:
        user = get_user_model().objects.get(pk=user_id)
    except get_user_model().DoesNotExist:
        return Response({'error': 'Sesión no válida'}, status=status.HTTP_401_UNAUTHORIZED)
    session_hash = store.get('_auth_user_hash')
    if session_hash and session_hash != user.get_session_auth_hash():
        return Response({'error': 'Sesión no válida'}, status=status.HTTP_401_UNAUTHORIZED)
    if not user.is_active:
        return Response({'error': 'Usuario inactivo'}, status=status.HTTP_403_FORBIDDEN)
    token, _ = Token.objects.get_or_create(user=user)
    return Response({'token': token.key, 'email': user.email, 'full_name': user.full_name})


def _log_extension_login(request, user):
    from .utils import parse_user_agent, get_client_ip
    user_agent = request.META.get('HTTP_USER_AGENT', '')
    parsed = parse_user_agent(user_agent)
    ip = get_client_ip(request)
    LoginHistory.objects.create(user=user, ip_address=ip, user_agent=user_agent,
                                 browser='Extensión', os=parsed['os'], device='Chrome',
                                 success=True, session_key='extension')
