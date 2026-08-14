import ipaddress
import logging

import requests
from django.utils import timezone
from datetime import timedelta

from .models import IPGeoCache

logger = logging.getLogger(__name__)

API_URL = 'http://ip-api.com/json/{ip}?fields=status,country,countryCode'
CACHE_MAX_AGE = timedelta(days=30)


def _is_private(ip):
    try:
        addr = ipaddress.ip_address(ip)
        return addr.is_private or addr.is_loopback or addr.is_link_local
    except ValueError:
        return True


def get_country_for_ip(ip_address):
    """Return {'country_name', 'country_code'} resolving via ip-api.com, cached in DB."""
    ip = (ip_address or '').strip()
    empty = {'country_name': '', 'country_code': ''}
    if not ip:
        return empty
    if _is_private(ip):
        return {'country_name': 'Local', 'country_code': 'XX'}

    cached = IPGeoCache.objects.filter(ip_address=ip).first()
    if cached and (timezone.now() - cached.resolved_at) < CACHE_MAX_AGE:
        return {'country_name': cached.country_name, 'country_code': cached.country_code}

    country_name = ''
    country_code = ''
    try:
        resp = requests.get(API_URL.format(ip=ip), timeout=5)
        data = resp.json()
        if data.get('status') == 'success':
            country_name = data.get('country', '') or ''
            country_code = data.get('countryCode', '') or ''
    except Exception as exc:  # noqa: BLE001
        logger.warning('Geo lookup failed for %s: %s', ip, exc)

    IPGeoCache.objects.update_or_create(
        ip_address=ip,
        defaults={
            'country_name': country_name,
            'country_code': country_code,
            'resolved_at': timezone.now(),
        },
    )
    return {'country_name': country_name, 'country_code': country_code}
