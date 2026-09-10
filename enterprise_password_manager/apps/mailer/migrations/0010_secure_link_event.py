from django.db import migrations


def add_link_event(apps, schema_editor):
    NotificationEvent = apps.get_model('mailer', 'NotificationEvent')
    EmailTemplate = apps.get_model('mailer', 'EmailTemplate')

    event, created = NotificationEvent.objects.get_or_create(
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

    EmailTemplate.objects.get_or_create(
        event=event,
        defaults={
            'subject': 'Te compartieron un enlace temporal: {{ nombre_servicio }}',
            'body_html': (
                '<p>Hola,</p>'
                '<p><strong>{{ nombre_empresa }}</strong> te compartió un enlace temporal '
                'para acceder a <strong>{{ nombre_servicio }}</strong>.</p>'
                '<p>El enlace es válido por tiempo limitado. No lo compartas con nadie más.</p>'
                '<p style="text-align:center;margin:24px 0;">'
                '<a href="{{ url }}" style="background-color:#0d6efd;color:#ffffff;'
                'padding:12px 28px;text-decoration:none;border-radius:6px;display:inline-block;">'
                'Abrir enlace temporal</a></p>'
                '<p>Si el enlace no funciona, copia esta dirección en tu navegador:<br>'
                '<a href="{{ url }}">{{ url }}</a></p>'
                '<p>Fecha: {{ fecha }} - Hora: {{ hora }}</p>'
            ),
            'body_text': (
                'Te compartieron un enlace temporal para acceder a {{ nombre_servicio }} '
                'desde {{ nombre_empresa }}.\n'
                'El enlace es válido por tiempo limitado.\n\n'
                'Abrir enlace: {{ url }}\n\n'
                'Fecha: {{ fecha }} - Hora: {{ hora }}'
            ),
        },
    )


def remove_link_event(apps, schema_editor):
    NotificationEvent = apps.get_model('mailer', 'NotificationEvent')
    NotificationEvent.objects.filter(code='link_shared').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('mailer', '0009_secret_expired_event'),
    ]

    operations = [
        migrations.RunPython(add_link_event, remove_link_event),
    ]