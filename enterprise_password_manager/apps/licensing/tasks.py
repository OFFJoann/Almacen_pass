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
