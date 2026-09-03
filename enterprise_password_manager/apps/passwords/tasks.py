from celery import shared_task
from django.core.cache import cache
from django.utils import timezone

from apps.passwords.encryption import check_hibp


@shared_task
def check_entry_hibp(entry_id):
    from apps.passwords.models import PasswordEntry

    try:
        entry = PasswordEntry.objects.filter(pk=entry_id, is_deleted=False).get()
    except PasswordEntry.DoesNotExist:
        return

    cache_key = f"hibp:entry:{entry.pk}"
    if cache.get(cache_key):
        return

    password = entry.get_password()
    if not password:
        return

    count = 0
    try:
        count = check_hibp(password)
    except Exception:
        count = 0

    PasswordEntry.objects.filter(pk=entry.pk).update(
        is_compromised=count > 0,
        compromised_count=count,
        compromised_checked_at=timezone.now(),
    )

    cache.set(cache_key, True, timeout=60 * 60 * 24)
