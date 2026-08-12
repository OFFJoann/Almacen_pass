import re
import hashlib
import hmac
import json
from importlib import import_module
from urllib.parse import urlencode
from django.conf import settings
from django.utils import timezone
from apps.users.models import ActiveSession


def session_is_active(session_key):
    """True si la clave de sesión aún tiene datos válidos en el backend de sesiones."""
    engine = import_module(settings.SESSION_ENGINE)
    store = engine.SessionStore(session_key=session_key)
    try:
        return bool(store.load())
    except Exception:
        return False


def user_has_active_session(user):
    """True si el usuario tiene al menos una sesión activa no vencida."""
    now = timezone.now()
    for s in ActiveSession.objects.filter(user=user).exclude(session_key=''):
        if s.expires_at and s.expires_at > now and session_is_active(s.session_key):
            return True
    return False


def parse_user_agent(user_agent):
    result = {'browser': 'Unknown', 'os': 'Unknown', 'device': 'Desktop'}
    if not user_agent:
        return result
    ua = user_agent.lower()
    if 'firefox' in ua and 'gecko' in ua:
        result['browser'] = 'Firefox'
    elif 'chrome' in ua and 'edge' not in ua and 'opr' not in ua:
        result['browser'] = 'Chrome'
    elif 'safari' in ua and 'chrome' not in ua:
        result['browser'] = 'Safari'
    elif 'edge' in ua:
        result['browser'] = 'Edge'
    elif 'opr' in ua or 'opera' in ua:
        result['browser'] = 'Opera'
    if 'windows' in ua:
        result['os'] = 'Windows'
    elif 'mac' in ua and 'iphone' not in ua and 'ipad' not in ua:
        result['os'] = 'macOS'
    elif 'linux' in ua:
        result['os'] = 'Linux'
    elif 'android' in ua:
        result['os'] = 'Android'
        result['device'] = 'Mobile'
    elif 'iphone' in ua or 'ipad' in ua:
        result['os'] = 'iOS'
        result['device'] = 'Mobile'
    if 'mobile' in ua or 'android' in ua or 'iphone' in ua:
        result['device'] = 'Mobile'
    elif 'tablet' in ua or 'ipad' in ua:
        result['device'] = 'Tablet'
    return result


def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', '')
    return ip


def verify_hibp_password(password):
    sha1_hash = hashlib.sha1(password.encode()).hexdigest().upper()
    prefix, suffix = sha1_hash[:5], sha1_hash[5:]
    try:
        import requests
        response = requests.get(
            f'https://api.pwnedpasswords.com/range/{prefix}',
            timeout=5
        )
        if response.status_code == 200:
            hashes = [line.split(':') for line in response.text.splitlines()]
            for h, count in hashes:
                if h == suffix:
                    return int(count)
    except Exception:
        pass
    return 0
