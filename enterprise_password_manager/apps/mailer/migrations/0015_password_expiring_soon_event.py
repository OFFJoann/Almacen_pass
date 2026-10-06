from django.db import migrations


def add_password_expiring_soon_event(apps, schema_editor):
    NotificationEvent = apps.get_model('mailer', 'NotificationEvent')
    EmailTemplate = apps.get_model('mailer', 'EmailTemplate')

    event, created = NotificationEvent.objects.get_or_create(
        code='password_expiring_soon',
        defaults={
            'name': 'Contraseña próxima a vencer',
            'description': 'Un registro de la bóveda vencerá en menos de 5 días.',
            'category': 'password',
            'icon': 'hourglass-split',
            'order': 9,
            'is_personal': True,
            'available_variables': [
                'nombre_empresa', 'usuario', 'nombre_servicio', 'dominio',
                'fecha_vencimiento', 'dias_restantes', 'url', 'fecha', 'hora',
            ],
        },
    )

    EmailTemplate.objects.get_or_create(
        event=event,
        defaults={
            'subject': 'AVISO: Registro próximo a vencer - {{ nombre_servicio }}',
            'body_html': (
                '<h3>Registro próximo a vencer</h3>'
                '<p>El registro <strong>{{ nombre_servicio }}</strong> '
                '(usuario {{ usuario }}, dominio {{ dominio }}) vence el '
                '<strong>{{ fecha_vencimiento }}</strong>.</p>'
                '<p>Quedan <strong>{{ dias_restantes }}</strong> día(s). '
                'Si no lo renuevas, quedará marcado como <strong>vencido</strong>.</p>'
                '<p>Fecha de la alerta: {{ fecha }} - Hora: {{ hora }}</p>'
            ),
            'body_text': (
                'AVISO: Registro próximo a vencer\n'
                'El registro {{ nombre_servicio }} (usuario {{ usuario }}, '
                'dominio {{ dominio }}) vence el {{ fecha_vencimiento }}.\n'
                'Quedan {{ dias_restantes }} día(s). '
                'Si no lo renuevas, quedará marcado como vencido.\n'
                'Fecha de la alerta: {{ fecha }} - Hora: {{ hora }}'
            ),
        },
    )


def remove_password_expiring_soon_event(apps, schema_editor):
    NotificationEvent = apps.get_model('mailer', 'NotificationEvent')
    NotificationEvent.objects.filter(code='password_expiring_soon').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('mailer', '0014_schedule_expiry_checks'),
    ]

    operations = [
        migrations.RunPython(add_password_expiring_soon_event, remove_password_expiring_soon_event),
    ]
