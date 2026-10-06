from django.db import migrations


def add_secret_expiring_soon_event(apps, schema_editor):
    NotificationEvent = apps.get_model('mailer', 'NotificationEvent')
    EmailTemplate = apps.get_model('mailer', 'EmailTemplate')

    event, created = NotificationEvent.objects.get_or_create(
        code='secret_expiring_soon',
        defaults={
            'name': 'Secreto próximo a vencer',
            'description': 'Un secreto vencerá en menos de 5 días.',
            'category': 'secret',
            'icon': 'hourglass-split',
            'order': 17,
            'is_personal': True,
            'available_variables': [
                'nombre_empresa', 'usuario', 'nombre_secreto', 'tipo',
                'fecha_vencimiento', 'dias_restantes', 'fecha', 'hora',
            ],
        },
    )

    EmailTemplate.objects.get_or_create(
        event=event,
        defaults={
            'subject': 'AVISO: Secreto próximo a vencer - {{ nombre_secreto }}',
            'body_html': (
                '<h3>Secreto próximo a vencer</h3>'
                '<p>El secreto <strong>{{ nombre_secreto }}</strong> '
                '(tipo {{ tipo }}, usuario {{ usuario }}) vence el '
                '<strong>{{ fecha_vencimiento }}</strong>.</p>'
                '<p>Quedan <strong>{{ dias_restantes }}</strong> día(s). '
                'Si no lo renuevas, quedará marcado como <strong>vencido</strong>.</p>'
                '<p>Fecha de la alerta: {{ fecha }} - Hora: {{ hora }}</p>'
            ),
            'body_text': (
                'AVISO: Secreto próximo a vencer\n'
                'El secreto {{ nombre_secreto }} (tipo {{ tipo }}, usuario {{ usuario }}) '
                'vence el {{ fecha_vencimiento }}.\n'
                'Quedan {{ dias_restantes }} día(s). '
                'Si no lo renuevas, quedará marcado como vencido.\n'
                'Fecha de la alerta: {{ fecha }} - Hora: {{ hora }}'
            ),
        },
    )


def remove_secret_expiring_soon_event(apps, schema_editor):
    NotificationEvent = apps.get_model('mailer', 'NotificationEvent')
    NotificationEvent.objects.filter(code='secret_expiring_soon').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('mailer', '0012_rename_reshare_events'),
    ]

    operations = [
        migrations.RunPython(add_secret_expiring_soon_event, remove_secret_expiring_soon_event),
    ]
