from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
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
