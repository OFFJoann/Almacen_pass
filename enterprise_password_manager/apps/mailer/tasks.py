from celery import shared_task
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


def check_expired_passwords():
    """Notify groups subscribed to 'password_expired' for each expired password."""
    from apps.passwords.models import PasswordEntry
    from .services import notify_event, domain_from_url

    now = timezone.now()
    entries = PasswordEntry.objects.filter(
        is_deleted=False,
        is_obsolete=False,
        expires_at__isnull=False,
        expires_at__lte=now,
        expiry_notified_at__isnull=True,
    ).select_related('vault__user')

    notified = 0
    for entry in entries:
        try:
            email = entry.vault.user.email
        except Exception:
            email = ''
        sent = notify_event('password_expired', {
            'usuario': email,
            'nombre_servicio': entry.name,
            'dominio': domain_from_url(entry.url),
            'url': entry.url or '/',
            'riesgo_actual': entry.get_sensitivity_display(),
        })
        if sent:
            entry.expiry_notified_at = timezone.now()
            entry.save(update_fields=['expiry_notified_at'])
            notified += 1
    if notified:
        from apps.audit.models import AuditLog
        AuditLog.objects.create(
            user=None,
            action='SETTINGS_CHANGED',
            details=_('Se notificaron %(count)s contraseña(s) vencida(s).') % {'count': notified},
            result='success',
        )
    return notified


@shared_task
def check_expired_passwords_task():
    return check_expired_passwords()
