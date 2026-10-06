from django.db import migrations


def speed_up_expiry_checks(apps, schema_editor):
    """Cada 5 minutos en vez de cada hora.

    El usuario espera el aviso "en el momento" en que vence, así que con una
    hora de intervalo el correo podía llegar hasta 60 minutos tarde.
    """
    IntervalSchedule = apps.get_model('django_celery_beat', 'IntervalSchedule')
    PeriodicTask = apps.get_model('django_celery_beat', 'PeriodicTask')

    interval, _ = IntervalSchedule.objects.get_or_create(
        every=300, period='seconds',
    )
    updated = PeriodicTask.objects.filter(name='check-expiry-hourly').update(
        interval=interval, enabled=True,
    )
    if not updated:
        PeriodicTask.objects.create(
            name='check-expiry-hourly',
            task='apps.mailer.tasks.check_expired_passwords_task',
            interval=interval,
            enabled=True,
        )


def restore_hourly(apps, schema_editor):
    IntervalSchedule = apps.get_model('django_celery_beat', 'IntervalSchedule')
    PeriodicTask = apps.get_model('django_celery_beat', 'PeriodicTask')
    interval, _ = IntervalSchedule.objects.get_or_create(
        every=3600, period='seconds',
    )
    PeriodicTask.objects.filter(name='check-expiry-hourly').update(interval=interval)


class Migration(migrations.Migration):

    dependencies = [
        ('mailer', '0015_password_expiring_soon_event'),
    ]

    operations = [
        migrations.RunPython(speed_up_expiry_checks, restore_hourly),
    ]
