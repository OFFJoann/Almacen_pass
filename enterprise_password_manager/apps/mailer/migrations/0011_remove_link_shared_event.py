from django.db import migrations


def remove_link_event(apps, schema_editor):
    NotificationEvent = apps.get_model('mailer', 'NotificationEvent')
    NotificationEvent.objects.filter(code='link_shared').delete()


def restore_link_event(apps, schema_editor):
    NotificationEvent = apps.get_model('mailer', 'NotificationEvent')
    NotificationEvent.objects.get_or_create(
        code='link_shared',
        defaults={
            'name': 'Enlace temporal compartido',
            'description': 'Un enlace temporal (pwpush) se compartió por correo con un destinatario externo.',
            'category': 'password',
            'icon': 'link-45deg',
            'is_personal': True,
            'order': 18,
            'available_variables': [
                'nombre_empresa', 'usuario', 'nombre_servicio', 'dominio',
                'fecha', 'hora', 'url',
            ],
        },
    )


class Migration(migrations.Migration):

    dependencies = [
        ('mailer', '0010_secure_link_event'),
    ]

    operations = [
        migrations.RunPython(remove_link_event, restore_link_event),
    ]