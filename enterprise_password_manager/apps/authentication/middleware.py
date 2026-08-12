import re
from django.contrib.auth import logout
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from apps.users.models import ActiveSession
from apps.authentication.utils import parse_user_agent


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
