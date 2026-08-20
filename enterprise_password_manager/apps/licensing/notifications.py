from django.utils import timezone
from apps.mailer.services import notify_event

LICENSE_EXPIRY_WARNING_DAYS = 30


def _dias_restantes(expires_at):
    if not expires_at:
        return None
    return (expires_at.date() - timezone.localtime().date()).days


def evaluate_license_notifications(lic, updated=False):
    """Dispara las notificaciones de administración según el estado de la licencia.

    - license_updated: se envió cuando la licencia fue revalidada/actualizada.
    - license_expiring: se envía una sola vez cuando falta poco para vencer.

    ``updated`` debe ser True cuando la licencia se acaba de revalidar/activar.
    La función ajusta ``lic.expiry_alert_sent``; quien llame debe guardar el modelo.
    """
    sent = 0

    if not lic.is_valid:
        lic.expiry_alert_sent = False
        return sent

    if updated:
        sent += notify_event('license_updated', {
            'empresa': lic.company,
            'max_usuarios': lic.max_users if lic.max_users is not None else '',
            'fecha_expiracion': lic.expires_at.strftime('%d/%m/%Y') if lic.expires_at else '',
            'dias_restantes': _dias_restantes(lic.expires_at),
        })

    if lic.expires_at:
        dias = _dias_restantes(lic.expires_at)
        if dias is not None and 0 <= dias <= LICENSE_EXPIRY_WARNING_DAYS:
            if not lic.expiry_alert_sent:
                sent += notify_event('license_expiring', {
                    'empresa': lic.company,
                    'fecha_expiracion': lic.expires_at.strftime('%d/%m/%Y'),
                    'dias_restantes': dias,
                })
                lic.expiry_alert_sent = True
        else:
            lic.expiry_alert_sent = False

    return sent
