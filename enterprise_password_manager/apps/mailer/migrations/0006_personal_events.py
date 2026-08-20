from django.db import migrations


def mark_personal_events(apps, schema_editor):
    NotificationEvent = apps.get_model('mailer', 'NotificationEvent')
    EmailTemplate = apps.get_model('mailer', 'EmailTemplate')

    new_events = [
        {
            'code': 'reshare_requested',
            'name': 'Solicitud de re-compartición',
            'description': 'Un usuario solicitó re-compartir una contraseña con otro usuario.',
            'category': 'password',
            'icon': 'share',
            'order': 13,
            'available_variables': ['nombre_empresa', 'solicitante', 'nombre_servicio', 'compartido_con', 'fecha', 'hora'],
        },
        {
            'code': 'reshare_approved',
            'name': 'Re-compartición aprobada',
            'description': 'Se aprobó una solicitud de re-compartición de una contraseña.',
            'category': 'password',
            'icon': 'check2-circle',
            'order': 14,
            'available_variables': ['nombre_empresa', 'nombre_servicio', 'compartido_con', 'fecha', 'hora'],
        },
    ]

    templates = {
        'reshare_requested': {
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

    for item in new_events:
        event, created = NotificationEvent.objects.get_or_create(
            code=item['code'], defaults=item
        )
        if created:
            tpl = templates.get(item['code'], {})
            EmailTemplate.objects.create(
                event=event,
                subject=tpl.get('subject', item['name']),
                body_html=tpl.get('body_html', f'<h3>{item["name"]}</h3>'),
                body_text=tpl.get('body_text', item['name']),
            )

    # Estas notificaciones son personales/estáticas: siempre llegan al usuario estándar involucrado.
    personal_codes = [
        'password_shared',
        'password_compromised',
        'password_deleted',
        'reshare_requested',
        'reshare_approved',
    ]
    NotificationEvent.objects.filter(code__in=personal_codes).update(is_personal=True)


def unmark_personal_events(apps, schema_editor):
    NotificationEvent = apps.get_model('mailer', 'NotificationEvent')
    NotificationEvent.objects.filter(
        code__in=['reshare_requested', 'reshare_approved']
    ).delete()
    NotificationEvent.objects.filter(
        code__in=['password_shared', 'password_compromised', 'password_deleted']
    ).update(is_personal=False)


class Migration(migrations.Migration):

    dependencies = [
        ('mailer', '0005_notificationevent_is_personal'),
    ]

    operations = [
        migrations.RunPython(mark_personal_events, unmark_personal_events),
    ]
