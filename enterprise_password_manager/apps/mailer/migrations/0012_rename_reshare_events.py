from django.db import migrations


def rename_reshare_events(apps, schema_editor):
    NotificationEvent = apps.get_model('mailer', 'NotificationEvent')
    EmailTemplate = apps.get_model('mailer', 'EmailTemplate')

    updates = {
        'reshare_requested': {
            'name': 'Solicitud de compartir',
            'description': 'Un usuario solicitó compartir una contraseña con otro usuario.',
            'subject': 'Solicitud de compartir - {{ nombre_servicio }}',
            'body_html': (
                '<h3>Solicitud de compartir</h3>'
                '<p><strong>{{ solicitante }}</strong> solicita compartir la contraseña '
                'de <strong>{{ nombre_servicio }}</strong> con <strong>{{ compartido_con }}</strong>.</p>'
                '<p>Fecha: {{ fecha }} - Hora: {{ hora }}</p>'
            ),
            'body_text': (
                'Solicitud de compartir\n'
                '{{ solicitante }} solicita compartir la contraseña de {{ nombre_servicio }} con {{ compartido_con }}.\n'
                'Fecha: {{ fecha }} - Hora: {{ hora }}'
            ),
        },
        'reshare_approved': {
            'name': 'Compartición aprobada',
            'description': 'Se aprobó una solicitud de compartir una contraseña.',
            'subject': 'Compartición aprobada - {{ nombre_servicio }}',
            'body_html': (
                '<h3>Compartición aprobada</h3>'
                '<p>Tu solicitud para compartir <strong>{{ nombre_servicio }}</strong> con '
                '<strong>{{ compartido_con }}</strong> fue aprobada.</p>'
                '<p>Fecha: {{ fecha }} - Hora: {{ hora }}</p>'
            ),
            'body_text': (
                'Compartición aprobada\n'
                'Tu solicitud para compartir {{ nombre_servicio }} con {{ compartido_con }} fue aprobada.\n'
                'Fecha: {{ fecha }} - Hora: {{ hora }}'
            ),
        },
    }

    for code, data in updates.items():
        event = NotificationEvent.objects.filter(code=code).first()
        if event:
            event.name = data['name']
            event.description = data['description']
            event.save(update_fields=['name', 'description'])
            try:
                tpl = event.template
            except EmailTemplate.DoesNotExist:
                continue
            tpl.subject = data['subject']
            tpl.body_html = data['body_html']
            tpl.body_text = data['body_text']
            tpl.save(update_fields=['subject', 'body_html', 'body_text'])


def reverse_rename(apps, schema_editor):
    NotificationEvent = apps.get_model('mailer', 'NotificationEvent')
    EmailTemplate = apps.get_model('mailer', 'EmailTemplate')

    updates = {
        'reshare_requested': {
            'name': 'Solicitud de re-compartición',
            'description': 'Un usuario solicitó re-compartir una contraseña con otro usuario.',
            'subject': 'Solicitud de re-compartición - {{ nombre_servicio }}',
            'body_html': (
                '<h3>Solicitud de re-compartición</h3>'
                '<p><strong>{{ solicitante }}</strong> solicita compartir la contraseña '
                'de <strong>{{ nombre_servicio }}</strong> con <strong>{{ compartido_con }}</strong>.</p>'
                '<p>Fecha: {{ fecha }} - Hora: {{ hora }}</p>'
            ),
            'body_text': (
                'Solicitud de re-compartición\n'
                '{{ solicitante }} solicita compartir la contraseña de {{ nombre_servicio }} con {{ compartido_con }}.\n'
                'Fecha: {{ fecha }} - Hora: {{ hora }}'
            ),
        },
        'reshare_approved': {
            'name': 'Re-compartición aprobada',
            'description': 'Se aprobó una solicitud de re-compartición de una contraseña.',
            'subject': 'Re-compartición aprobada - {{ nombre_servicio }}',
            'body_html': (
                '<h3>Re-compartición aprobada</h3>'
                '<p>Tu solicitud para compartir <strong>{{ nombre_servicio }}</strong> con '
                '<strong>{{ compartido_con }}</strong> fue aprobada.</p>'
                '<p>Fecha: {{ fecha }} - Hora: {{ hora }}</p>'
            ),
            'body_text': (
                'Re-compartición aprobada\n'
                'Tu solicitud para compartir {{ nombre_servicio }} con {{ compartido_con }} fue aprobada.\n'
                'Fecha: {{ fecha }} - Hora: {{ hora }}'
            ),
        },
    }

    for code, data in updates.items():
        event = NotificationEvent.objects.filter(code=code).first()
        if event:
            event.name = data['name']
            event.description = data['description']
            event.save(update_fields=['name', 'description'])
            try:
                tpl = event.template
            except EmailTemplate.DoesNotExist:
                continue
            tpl.subject = data['subject']
            tpl.body_html = data['body_html']
            tpl.body_text = data['body_text']
            tpl.save(update_fields=['subject', 'body_html', 'body_text'])


class Migration(migrations.Migration):

    dependencies = [
        ('mailer', '0011_remove_link_shared_event'),
    ]

    operations = [
        migrations.RunPython(rename_reshare_events, reverse_rename),
    ]