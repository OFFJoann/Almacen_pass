from django.db import migrations


def add_expiry_check_schedule(apps, schema_editor):
    """Agenda la revisión de vencimientos de contraseñas y secretos.

    Cada hora revisa: contraseñas/secretos ya vencidos y secretos que vencen
    en menos de 5 días (aviso previo). Idempotente: si ya existe no hace nada.
    """
    IntervalSchedule = apps.get_model('django_celery_beat', 'IntervalSchedule')
    PeriodicTask = apps.get_model('django_celery_beat', 'PeriodicTask')

    interval, _ = IntervalSchedule.objects.get_or_create(
        every=3600, period='seconds',
        defaults={'name': 'Cada hora'},
    )
    PeriodicTask.objects.get_or_create(
        name='check-expiry-hourly',
        defaults={
            'task': 'apps.mailer.tasks.check_expired_passwords_task',
            'interval': interval,
            'enabled': True,
        },
    )


def remove_expiry_check_schedule(apps, schema_editor):
    PeriodicTask = apps.get_model('django_celery_beat', 'PeriodicTask')
    PeriodicTask.objects.filter(name='check-expiry-hourly').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('mailer', '0013_secret_expiring_soon_event'),
        ('django_celery_beat', '0018_improve_crontab_helptext'),
    ]

    operations = [
        migrations.RunPython(add_expiry_check_schedule, remove_expiry_check_schedule),
    ]
