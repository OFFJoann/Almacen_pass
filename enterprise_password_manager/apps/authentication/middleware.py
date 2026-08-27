import re
from django.contrib.auth import logout
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from apps.users.models import ActiveSession
from apps.authentication.utils import parse_user_agent


PUBLIC_PREFIXES = (
    '/auth/',
    '/sso/login',
    '/sso/callback',
    '/admin/',
    '/api/',
    '/__debug__/',
    '/static/',
    '/media/',
)


class RequireLoginMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.path.startswith(PUBLIC_PREFIXES):
            if not request.user.is_authenticated:
                login_url = reverse(settings.LOGIN_URL)
                return redirect(f'{login_url}?next={request.path}', permanent=True)
        return self.get_response(request)


class SecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
        if not settings.DEBUG:
            response['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains; preload'
        return response


class SessionSecurityMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            now = timezone.now()
            session_key = request.session.session_key

            ActiveSession.objects.filter(
                user=request.user,
                expires_at__lt=now
            ).delete()

            if session_key:
                is_registered = ActiveSession.objects.filter(
                    user=request.user,
                    session_key=session_key,
                    expires_at__gt=now,
                ).exists()
                if not is_registered:
                    messages.error(
                        request,
                        _('Solo se permite una sesión activa. Tu sesión se cerró porque se inició sesión desde otro dispositivo o navegador.'),
                    )
                    logout(request)
                    return HttpResponseRedirect(reverse('authentication:login'))
        return self.get_response(request)


class UpdateActivityMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            session_key = request.session.session_key
            if session_key:
                ActiveSession.objects.filter(
                    user=request.user,
                    session_key=session_key
                ).update(last_activity=timezone.now())
                User = request.user.__class__
                User.objects.filter(pk=request.user.pk).update(
                    last_activity=timezone.now()
                )
        return self.get_response(request)


class ForcePasswordChangeMiddleware:
    """Obliga a cambiar la contraseña temporal/forzada antes de navegar.

    Si el usuario autenticado tiene force_password_change=True, cualquier
    solicitud (salvo la propia página de cambio, el logout y la verificación
    MFA para completar el login) lo redirige a la página de cambio.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, 'user', None)
        if user is not None and user.is_authenticated and getattr(user, 'force_password_change', False):
            path = request.path
            # No redirigir peticiones de estáticos/media/api para no romper el render.
            if path.startswith(('/static/', '/media/', '/api/', '/__debug__/')):
                return self.get_response(request)
            allowed = (
                reverse('authentication:force_password_change'),
                reverse('authentication:logout'),
                reverse('authentication:mfa_verify'),
            )
            if path not in allowed:
                return redirect('authentication:force_password_change')
        return self.get_response(request)
