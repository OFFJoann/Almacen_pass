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


def check_expired_secrets():
    """Notify the owner (personal event) for each expired secret."""
    from apps.secrets.models import Secret
    from .services import notify_event

    now = timezone.now()
    secrets = Secret.objects.filter(
        is_deleted=False,
        is_obsolete=False,
        expires_at__isnull=False,
        expires_at__lte=now,
        expiry_notified_at__isnull=True,
    ).select_related('user')

    notified = 0
    for secret in secrets:
        email = secret.user.email
        if not email:
            continue
        sent = notify_event('secret_expired', {
            'usuario': email,
            'nombre_secreto': secret.name,
            'tipo': secret.get_type_display(),
            'fecha': now.date().isoformat(),
            'hora': now.time().strftime('%H:%M'),
        }, recipients=[email])
        if sent:
            secret.expiry_notified_at = timezone.now()
            secret.save(update_fields=['expiry_notified_at'])
            notified += 1
    if notified:
        from apps.audit.models import AuditLog
        AuditLog.objects.create(
            user=None,
            action='SETTINGS_CHANGED',
            details=_('Se notificaron %(count)s secreto(s) vencido(s).') % {'count': notified},
            result='success',
        )
    return notified


@shared_task
def check_expired_passwords_task():
    n1 = check_expired_passwords()
    n2 = check_expired_secrets()
    return n1 + n2
