from django.db import migrations


def add_secret_expired_event(apps, schema_editor):
    NotificationEvent = apps.get_model('mailer', 'NotificationEvent')
    EmailTemplate = apps.get_model('mailer', 'EmailTemplate')

    event, created = NotificationEvent.objects.get_or_create(
        code='secret_expired',
        defaults={
            'name': 'Secreto vencido',
            'description': 'Un secreto alcanzó su fecha de vencimiento configurada.',
            'category': 'secret',
            'icon': 'hourglass-split',
            'order': 18,
            'is_personal': True,
            'available_variables': [
                'nombre_empresa', 'usuario', 'nombre_secreto', 'tipo',
                'fecha', 'hora',
            ],
        },
    )

    EmailTemplate.objects.get_or_create(
        event=event,
        defaults={
            'subject': 'ALERTA: Secreto vencido - {{ nombre_secreto }}',
            'body_html': (
                '<h3>Secreto vencido</h3>'
                '<p>El secreto <strong>{{ nombre_secreto }}</strong> '
                '(tipo {{ tipo }}, usuario {{ usuario }}) alcanzó su fecha de vencimiento.</p>'
                '<p><strong>Se recomienda rotar o renovar este secreto.</strong></p>'
                '<p>Fecha: {{ fecha }} - Hora: {{ hora }}</p>'
            ),
            'body_text': (
                'ALERTA: Secreto vencido\n'
                'El secreto {{ nombre_secreto }} (tipo {{ tipo }}, usuario {{ usuario }}) '
                'alcanzó su fecha de vencimiento.\n'
                'Se recomienda rotar o renovar este secreto.\n'
                'Fecha: {{ fecha }} - Hora: {{ hora }}'
            ),
        },
    )


def remove_secret_expired_event(apps, schema_editor):
    NotificationEvent = apps.get_model('mailer', 'NotificationEvent')
    NotificationEvent.objects.filter(code='secret_expired').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('mailer', '0008_alter_smtpsettings_company_name_and_more'),
    ]

    operations = [
        migrations.RunPython(add_secret_expired_event, remove_secret_expired_event),
    ]
