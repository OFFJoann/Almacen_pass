from django.db import migrations


def add_license_events(apps, schema_editor):
    NotificationEvent = apps.get_model('mailer', 'NotificationEvent')
    EmailTemplate = apps.get_model('mailer', 'EmailTemplate')

    events = [
        {
            'code': 'license_expiring',
            'name': 'Licencia próxima a vencer',
            'description': 'La licencia de la instancia está próxima a vencer.',
            'category': 'system',
            'icon': 'clock-history',
            'order': 30,
            'available_variables': ['nombre_empresa', 'empresa', 'fecha_expiracion', 'dias_restantes', 'fecha', 'hora'],
            'subject': 'Licencia próxima a vencer - {{ empresa }}',
            'body_html': (
                '<h3>Licencia próxima a vencer</h3>'
                '<p>La licencia de <strong>{{ empresa }}</strong> expirará el '
                '<strong>{{ fecha_expiracion }}</strong> (quedan <strong>{{ dias_restantes }}</strong> días).</p>'
                '<p>Fecha: {{ fecha }} - Hora: {{ hora }}</p>'
            ),
            'body_text': (
                'Licencia próxima a vencer\n'
                'La licencia de {{ empresa }} expirará el {{ fecha_expiracion }} (quedan {{ dias_restantes }} días).\n'
                'Fecha: {{ fecha }} - Hora: {{ hora }}'
            ),
        },
        {
            'code': 'license_updated',
            'name': 'Licencia actualizada',
            'description': 'La licencia fue revalidada o actualizada.',
            'category': 'system',
            'icon': 'arrow-repeat',
            'order': 31,
            'available_variables': ['nombre_empresa', 'empresa', 'max_usuarios', 'fecha_expiracion', 'dias_restantes', 'fecha', 'hora'],
            'subject': 'Licencia actualizada - {{ empresa }}',
            'body_html': (
                '<h3>Licencia actualizada</h3>'
                '<p>La licencia de <strong>{{ empresa }}</strong> fue actualizada.</p>'
                '<p>Máximo de usuarios: {{ max_usuarios }}<br>Expira: {{ fecha_expiracion }}</p>'
                '<p>Fecha: {{ fecha }} - Hora: {{ hora }}</p>'
            ),
            'body_text': (
                'Licencia actualizada\n'
                'La licencia de {{ empresa }} fue actualizada.\n'
                'Máximo de usuarios: {{ max_usuarios }} - Expira: {{ fecha_expiracion }}\n'
                'Fecha: {{ fecha }} - Hora: {{ hora }}'
            ),
        },
    ]

    for item in events:
        event, created = NotificationEvent.objects.get_or_create(
            code=item['code'],
            defaults={
                'name': item['name'],
                'description': item['description'],
                'category': item['category'],
                'icon': item['icon'],
                'order': item['order'],
                'available_variables': item['available_variables'],
            },
        )
        if created:
            EmailTemplate.objects.create(
                event=event,
                subject=item['subject'],
                body_html=item['body_html'],
                body_text=item['body_text'],
            )


def remove_license_events(apps, schema_editor):
    NotificationEvent = apps.get_model('mailer', 'NotificationEvent')
    NotificationEvent.objects.filter(code__in=['license_expiring', 'license_updated']).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('mailer', '0006_personal_events'),
    ]

    operations = [
        migrations.RunPython(add_license_events, remove_license_events),
    ]
