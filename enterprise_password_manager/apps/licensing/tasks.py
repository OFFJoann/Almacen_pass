from celery import shared_task
from django.utils import timezone

from .models import License
from .notifications import evaluate_license_notifications


@shared_task
def check_license_expiry_task():
    """Tarea periódica (programable vía django-celery-beat) que revisa si la
    licencia está próxima a vencer y envía la notificación de administración."""
    lic = License.get_instance()
    before = lic.expiry_alert_sent
    evaluate_license_notifications(lic, updated=False)
    if lic.expiry_alert_sent != before:
        lic.save(update_fields=['expiry_alert_sent'])
    return lic.expiry_alert_sent


@shared_task
def sync_license_task():
    """Sincronización automática de la licencia con la API del proveedor (cada hora)."""
    lic = License.get_instance()
    if not lic.license_key or not lic.company:
        return 'no-license'
    valid, error = lic.sync()
    return 'synced' if valid else f'invalid:{error}'
