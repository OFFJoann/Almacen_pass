import uuid

from django.db import migrations


def add_expired_event(apps, schema_editor):
    NotificationEvent = apps.get_model('mailer', 'NotificationEvent')
    EmailTemplate = apps.get_model('mailer', 'EmailTemplate')

    event, created = NotificationEvent.objects.get_or_create(
        code='password_expired',
        defaults={
            'name': 'Contraseña vencida',
            'description': 'Una contraseña alcanzó su fecha de vencimiento configurada.',
            'category': 'password',
            'icon': 'hourglass-split',
            'order': 17,
            'available_variables': [
                'nombre_empresa', 'usuario', 'nombre_servicio', 'dominio',
                'fecha', 'hora', 'url',
            ],
        },
    )

    EmailTemplate.objects.get_or_create(
        event=event,
        defaults={
            'subject': 'ALERTA: Contraseña vencida - {{ nombre_servicio }}',
            'body_html': (
                '<h3>Contraseña vencida</h3>'
                '<p>La contraseña de <strong>{{ nombre_servicio }}</strong> '
                '(usuario {{ usuario }}) alcanzó su fecha de vencimiento.</p>'
                '<p><strong>Se recomienda generar y guardar una nueva contraseña.</strong></p>'
                '<p>Fecha: {{ fecha }} - Hora: {{ hora }}</p>'
                '<p>{% if url %}<a href="{{ url }}">Ver contraseña</a>{% endif %}</p>'
            ),
            'body_text': (
                'ALERTA: Contraseña vencida\n'
                'La contraseña de {{ nombre_servicio }} (usuario {{ usuario }}) alcanzó su fecha de vencimiento.\n'
                'Se recomienda generar y guardar una nueva contraseña.\n'
                'Fecha: {{ fecha }} - Hora: {{ hora }}'
            ),
        },
    )


def remove_expired_event(apps, schema_editor):
    NotificationEvent = apps.get_model('mailer', 'NotificationEvent')
    NotificationEvent.objects.filter(code='password_expired').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('mailer', '0002_seed_events'),
    ]

    operations = [
        migrations.RunPython(add_expired_event, remove_expired_event),
    ]
