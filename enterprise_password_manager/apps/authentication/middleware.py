import re
from django.utils import timezone
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
                ua = request.META.get('HTTP_USER_AGENT', '')
                ActiveSession.objects.filter(
                    user=request.user, user_agent=ua
                ).exclude(session_key=session_key).delete()
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
