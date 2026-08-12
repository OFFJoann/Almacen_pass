import uuid

from django.db import migrations


def seed_events(apps, schema_editor):
    NotificationEvent = apps.get_model('mailer', 'NotificationEvent')
    EmailTemplate = apps.get_model('mailer', 'EmailTemplate')

    events = [
        {
            'code': 'domain_risk_increased',
            'name': 'Incremento del riesgo general de un dominio',
            'description': 'El riesgo general de un dominio monitoreado aumentó.',
            'category': 'domain',
            'icon': 'graph-up-arrow',
            'order': 1,
            'available_variables': ['nombre_empresa', 'dominio', 'riesgo_actual', 'riesgo_anterior', 'fecha', 'hora', 'url'],
        },
        {
            'code': 'domain_risk_decreased',
            'name': 'Disminución del riesgo general',
            'description': 'El riesgo general de un dominio monitoreado disminuyó.',
            'category': 'domain',
            'icon': 'graph-down-arrow',
            'order': 2,
            'available_variables': ['nombre_empresa', 'dominio', 'riesgo_actual', 'riesgo_anterior', 'fecha', 'hora', 'url'],
        },
        {
            'code': 'password_created',
            'name': 'Se creó una nueva contraseña',
            'description': 'Un usuario guardó una nueva contraseña en su bóveda.',
            'category': 'password',
            'icon': 'key',
            'order': 10,
            'available_variables': ['nombre_empresa', 'usuario', 'nombre_servicio', 'dominio', 'url', 'fecha', 'hora'],
        },
        {
            'code': 'password_modified',
            'name': 'Se modificó una contraseña',
            'description': 'Un usuario modificó una contraseña existente.',
            'category': 'password',
            'icon': 'pencil',
            'order': 11,
            'available_variables': ['nombre_empresa', 'usuario', 'nombre_servicio', 'dominio', 'url', 'fecha', 'hora'],
        },
        {
            'code': 'password_deleted',
            'name': 'Se eliminó una contraseña',
            'description': 'Un usuario eliminó una contraseña (enviada a la papelera o eliminada).',
            'category': 'password',
            'icon': 'trash',
            'order': 12,
            'available_variables': ['nombre_empresa', 'usuario', 'nombre_servicio', 'dominio', 'fecha', 'hora'],
        },
        {
            'code': 'password_shared',
            'name': 'Se compartió una contraseña',
            'description': 'Una contraseña fue compartida con un usuario o grupo.',
            'category': 'password',
            'icon': 'share',
            'order': 13,
            'available_variables': ['nombre_empresa', 'compartido_por', 'compartido_con', 'nombre_servicio', 'url', 'fecha', 'hora'],
        },
        {
            'code': 'password_compromised',
            'name': 'Contraseña comprometida detectada',
            'description': 'Se detectó que una contraseña aparece en filtraciones de datos.',
            'category': 'security',
            'icon': 'exclamation-triangle',
            'order': 14,
            'available_variables': ['nombre_empresa', 'usuario', 'nombre_servicio', 'dominio', 'riesgo_actual', 'fecha', 'hora', 'url'],
        },
        {
            'code': 'secret_shared',
            'name': 'Se compartió un secreto',
            'description': 'Un secreto (API key, SSH key, etc.) fue compartido.',
            'category': 'secret',
            'icon': 'incognito',
            'order': 15,
            'available_variables': ['nombre_empresa', 'compartido_por', 'compartido_con', 'nombre_servicio', 'fecha', 'hora'],
        },
        {
            'code': 'share_revoked',
            'name': 'Se revocó una compartición',
            'description': 'Se revocó el acceso compartido a una contraseña o secreto.',
            'category': 'password',
            'icon': 'shield-x',
            'order': 16,
            'available_variables': ['nombre_empresa', 'usuario', 'compartido_con', 'nombre_servicio', 'fecha', 'hora'],
        },
        {
            'code': 'domain_added',
            'name': 'Se agregó un nuevo dominio',
            'description': 'Un nuevo dominio fue agregado al monitoreo.',
            'category': 'domain',
            'icon': 'globe2',
            'order': 3,
            'available_variables': ['nombre_empresa', 'dominio', 'url', 'fecha', 'hora'],
        },
        {
            'code': 'analysis_finished',
            'name': 'Finalizó un análisis',
            'description': 'Un análisis programado finalizó correctamente.',
            'category': 'analysis',
            'icon': 'check-circle',
            'order': 4,
            'available_variables': ['nombre_empresa', 'dominio', 'resultado', 'métrica', 'fecha', 'hora', 'url'],
        },
        {
            'code': 'analysis_error',
            'name': 'Error durante un análisis',
            'description': 'Un análisis falló o no pudo completarse.',
            'category': 'analysis',
            'icon': 'x-circle',
            'order': 5,
            'available_variables': ['nombre_empresa', 'dominio', 'error', 'fecha', 'hora'],
        },
        {
            'code': 'vulnerability_critical',
            'name': 'Se detectó una vulnerabilidad crítica',
            'description': 'Se encontró una vulnerabilidad crítica en un activo monitoreado.',
            'category': 'security',
            'icon': 'bug',
            'order': 6,
            'available_variables': ['nombre_empresa', 'dominio', 'vulnerabilidad', 'riesgo_actual', 'fecha', 'hora', 'url'],
        },
        {
            'code': 'user_invited',
            'name': 'Usuario invitado al sistema',
            'description': 'Se invitó o creó un nuevo usuario en la plataforma.',
            'category': 'user',
            'icon': 'person-plus',
            'order': 20,
            'available_variables': ['nombre_empresa', 'invitado', 'invitado_por', 'fecha', 'hora', 'url'],
        },
        {
            'code': 'user_created',
            'name': 'Usuario creado',
            'description': 'Un administrador creó un usuario nuevo.',
            'category': 'user',
            'icon': 'person-check',
            'order': 21,
            'available_variables': ['nombre_empresa', 'usuario', 'nuevo_estado', 'fecha', 'hora', 'url'],
        },
        {
            'code': 'user_deleted',
            'name': 'Usuario eliminado',
            'description': 'Un usuario fue eliminado de la plataforma.',
            'category': 'user',
            'icon': 'person-x',
            'order': 22,
            'available_variables': ['nombre_empresa', 'usuario', 'fecha', 'hora'],
        },
        {
            'code': 'login_failed',
            'name': 'Intento de acceso fallido',
            'description': 'Un intento de inicio de sesión falló (posible fuerza bruta).',
            'category': 'security',
            'icon': 'shield-lock',
            'order': 30,
            'available_variables': ['nombre_empresa', 'usuario', 'ip', 'fecha', 'hora'],
        },
        {
            'code': 'settings_changed',
            'name': 'Configuración del sistema modificada',
            'description': 'Se modificó una configuración sensible del sistema.',
            'category': 'system',
            'icon': 'gear',
            'order': 31,
            'available_variables': ['nombre_empresa', 'usuario', 'nuevo_estado', 'fecha', 'hora'],
        },
    ]

    defaults = {
        'password_created': {
            'subject': 'Se creó una nueva contraseña - {{ nombre_empresa }}',
            'body_html': (
                '<h3>Nueva contraseña registrada</h3>'
                '<p>El usuario <strong>{{ usuario }}</strong> guardó una nueva contraseña '
                'para <strong>{{ nombre_servicio }}</strong>.</p>'
                '<p>Fecha: {{ fecha }} - Hora: {{ hora }}</p>'
                '<p>Plataforma: {{ nombre_empresa }}</p>'
            ),
            'body_text': (
                'Nueva contraseña registrada\n'
                'El usuario {{ usuario }} guardó una nueva contraseña para {{ nombre_servicio }}.\n'
                'Fecha: {{ fecha }} - Hora: {{ hora }}\n'
                'Plataforma: {{ nombre_empresa }}'
            ),
        },
        'password_modified': {
            'subject': 'Se modificó una contraseña - {{ nombre_empresa }}',
            'body_html': (
                '<h3>Contraseña modificada</h3>'
                '<p>El usuario <strong>{{ usuario }}</strong> modificó la contraseña '
                'de <strong>{{ nombre_servicio }}</strong>.</p>'
                '<p>Fecha: {{ fecha }} - Hora: {{ hora }}</p>'
            ),
            'body_text': (
                'Contraseña modificada\n'
                'El usuario {{ usuario }} modificó la contraseña de {{ nombre_servicio }}.\n'
                'Fecha: {{ fecha }} - Hora: {{ hora }}'
            ),
        },
        'password_deleted': {
            'subject': 'Se eliminó una contraseña - {{ nombre_empresa }}',
            'body_html': (
                '<h3>Contraseña eliminada</h3>'
                '<p>El usuario <strong>{{ usuario }}</strong> eliminó la contraseña '
                'de <strong>{{ nombre_servicio }}</strong>.</p>'
                '<p>Fecha: {{ fecha }} - Hora: {{ hora }}</p>'
            ),
            'body_text': (
                'Contraseña eliminada\n'
                'El usuario {{ usuario }} eliminó la contraseña de {{ nombre_servicio }}.\n'
                'Fecha: {{ fecha }} - Hora: {{ hora }}'
            ),
        },
        'password_shared': {
            'subject': 'Contraseña compartida - {{ nombre_empresa }}',
            'body_html': (
                '<h3>Contraseña compartida</h3>'
                '<p><strong>{{ compartido_por }}</strong> compartió la contraseña de '
                '<strong>{{ nombre_servicio }}</strong> con <strong>{{ compartido_con }}</strong>.</p>'
                '<p>Fecha: {{ fecha }} - Hora: {{ hora }}</p>'
            ),
            'body_text': (
                'Contraseña compartida\n'
                '{{ compartido_por }} compartió la contraseña de {{ nombre_servicio }} con {{ compartido_con }}.\n'
                'Fecha: {{ fecha }} - Hora: {{ hora }}'
            ),
        },
        'password_compromised': {
            'subject': 'ALERTA: Contraseña comprometida - {{ nombre_servicio }}',
            'body_html': (
                '<h3>Contraseña comprometida</h3>'
                '<p>La contraseña de <strong>{{ nombre_servicio }}</strong> (usuario {{ usuario }}) '
                'fue encontrada en filtraciones de datos.</p>'
                '<p><strong>Recomendamos cambiar la contraseña inmediatamente.</strong></p>'
                '<p>Fecha: {{ fecha }} - Hora: {{ hora }}</p>'
            ),
            'body_text': (
                'ALERTA: Contraseña comprometida\n'
                'La contraseña de {{ nombre_servicio }} (usuario {{ usuario }}) fue encontrada en filtraciones de datos.\n'
                'Recomendamos cambiar la contraseña inmediatamente.\n'
                'Fecha: {{ fecha }} - Hora: {{ hora }}'
            ),
        },
        'secret_shared': {
            'subject': 'Secreto compartido - {{ nombre_empresa }}',
            'body_html': (
                '<h3>Secreto compartido</h3>'
                '<p><strong>{{ compartido_por }}</strong> compartió el secreto '
                '<strong>{{ nombre_servicio }}</strong> con <strong>{{ compartido_con }}</strong>.</p>'
                '<p>Fecha: {{ fecha }} - Hora: {{ hora }}</p>'
            ),
            'body_text': (
                'Secreto compartido\n'
                '{{ compartido_por }} compartió el secreto {{ nombre_servicio }} con {{ compartido_con }}.\n'
                'Fecha: {{ fecha }} - Hora: {{ hora }}'
            ),
        },
        'share_revoked': {
            'subject': 'Se revocó una compartición - {{ nombre_empresa }}',
            'body_html': (
                '<h3>Compartición revocada</h3>'
                '<p>El acceso a <strong>{{ nombre_servicio }}</strong> fue revocado para '
                '<strong>{{ compartido_con }}</strong>.</p>'
                '<p>Fecha: {{ fecha }} - Hora: {{ hora }}</p>'
            ),
            'body_text': (
                'Compartición revocada\n'
                'El acceso a {{ nombre_servicio }} fue revocado para {{ compartido_con }}.\n'
                'Fecha: {{ fecha }} - Hora: {{ hora }}'
            ),
        },
        'user_invited': {
            'subject': 'Nuevo usuario invitado - {{ nombre_empresa }}',
            'body_html': (
                '<h3>Usuario invitado</h3>'
                '<p><strong>{{ invitado }}</strong> fue invitado a la plataforma por '
                '<strong>{{ invitado_por }}</strong>.</p>'
                '<p>Fecha: {{ fecha }} - Hora: {{ hora }}</p>'
                '<p>{% if url %}<a href="{{ url }}">Acceder a la plataforma</a>{% endif %}</p>'
            ),
            'body_text': (
                'Usuario invitado\n'
                '{{ invitado }} fue invitado a la plataforma por {{ invitado_por }}.\n'
                'Fecha: {{ fecha }} - Hora: {{ hora }}'
            ),
        },
        'user_created': {
            'subject': 'Usuario creado - {{ nombre_empresa }}',
            'body_html': (
                '<h3>Usuario creado</h3>'
                '<p>El usuario <strong>{{ usuario }}</strong> fue creado por un administrador.</p>'
                '<p>Estado: {{ nuevo_estado }} - Fecha: {{ fecha }} - Hora: {{ hora }}</p>'
            ),
            'body_text': (
                'Usuario creado\n'
                'El usuario {{ usuario }} fue creado por un administrador.\n'
                'Estado: {{ nuevo_estado }} - Fecha: {{ fecha }} - Hora: {{ hora }}'
            ),
        },
        'user_deleted': {
            'subject': 'Usuario eliminado - {{ nombre_empresa }}',
            'body_html': (
                '<h3>Usuario eliminado</h3>'
                '<p>El usuario <strong>{{ usuario }}</strong> fue eliminado de la plataforma.</p>'
                '<p>Fecha: {{ fecha }} - Hora: {{ hora }}</p>'
            ),
            'body_text': (
                'Usuario eliminado\n'
                'El usuario {{ usuario }} fue eliminado de la plataforma.\n'
                'Fecha: {{ fecha }} - Hora: {{ hora }}'
            ),
        },
        'login_failed': {
            'subject': 'ALERTA: Intento de acceso fallido - {{ nombre_empresa }}',
            'body_html': (
                '<h3>Intento de acceso fallido</h3>'
                '<p>Hubo un intento de acceso fallido para el usuario <strong>{{ usuario }}</strong> '
                'desde la IP <strong>{{ ip }}</strong>.</p>'
                '<p>Fecha: {{ fecha }} - Hora: {{ hora }}</p>'
            ),
            'body_text': (
                'ALERTA: Intento de acceso fallido\n'
                'Hubo un intento de acceso fallido para el usuario {{ usuario }} desde la IP {{ ip }}.\n'
                'Fecha: {{ fecha }} - Hora: {{ hora }}'
            ),
        },
        'settings_changed': {
            'subject': 'Configuración del sistema modificada - {{ nombre_empresa }}',
            'body_html': (
                '<h3>Configuración modificada</h3>'
                '<p>El usuario <strong>{{ usuario }}</strong> modificó la configuración '
                'del sistema ({{ nuevo_estado }}).</p>'
                '<p>Fecha: {{ fecha }} - Hora: {{ hora }}</p>'
            ),
            'body_text': (
                'Configuración modificada\n'
                'El usuario {{ usuario }} modificó la configuración del sistema ({{ nuevo_estado }}).\n'
                'Fecha: {{ fecha }} - Hora: {{ hora }}'
            ),
        },
        'domain_risk_increased': {
            'subject': 'ALERTA: Riesgo aumentado en {{ dominio }}',
            'body_html': (
                '<h3>Incremento del riesgo general</h3>'
                '<p>El riesgo del dominio <strong>{{ dominio }}</strong> aumentó de '
                '<strong>{{ riesgo_anterior }}</strong> a <strong>{{ riesgo_actual }}</strong>.</p>'
                '<p>{% if url %}<a href="{{ url }}">Ver detalles</a>{% endif %}</p>'
            ),
            'body_text': (
                'ALERTA: Riesgo aumentado en {{ dominio }}\n'
                'El riesgo del dominio {{ dominio }} aumentó de {{ riesgo_anterior }} a {{ riesgo_actual }}.'
            ),
        },
        'domain_risk_decreased': {
            'subject': 'Riesgo disminuido en {{ dominio }}',
            'body_html': (
                '<h3>Disminución del riesgo general</h3>'
                '<p>El riesgo del dominio <strong>{{ dominio }}</strong> disminuyó de '
                '<strong>{{ riesgo_anterior }}</strong> a <strong>{{ riesgo_actual }}</strong>.</p>'
            ),
            'body_text': (
                'Riesgo disminuido en {{ dominio }}\n'
                'El riesgo del dominio {{ dominio }} disminuyó de {{ riesgo_anterior }} a {{ riesgo_actual }}.'
            ),
        },
        'domain_added': {
            'subject': 'Nuevo dominio agregado - {{ nombre_empresa }}',
            'body_html': (
                '<h3>Nuevo dominio</h3>'
                '<p>El dominio <strong>{{ dominio }}</strong> fue agregado al monitoreo.</p>'
                '<p>Fecha: {{ fecha }} - Hora: {{ hora }}</p>'
            ),
            'body_text': (
                'Nuevo dominio\n'
                'El dominio {{ dominio }} fue agregado al monitoreo.\n'
                'Fecha: {{ fecha }} - Hora: {{ hora }}'
            ),
        },
        'analysis_finished': {
            'subject': 'Análisis finalizado - {{ dominio }}',
            'body_html': (
                '<h3>Análisis finalizado</h3>'
                '<p>El análisis de <strong>{{ dominio }}</strong> finalizó correctamente.</p>'
                '<p>Resultado: {{ resultado }} - Métrica: {{ métrica }}</p>'
            ),
            'body_text': (
                'Análisis finalizado\n'
                'El análisis de {{ dominio }} finalizó correctamente.\n'
                'Resultado: {{ resultado }} - Métrica: {{ métrica }}'
            ),
        },
        'analysis_error': {
            'subject': 'Error durante un análisis - {{ dominio }}',
            'body_html': (
                '<h3>Error durante un análisis</h3>'
                '<p>El análisis de <strong>{{ dominio }}</strong> falló.</p>'
                '<p>Detalle: {{ error }}</p>'
                '<p>Fecha: {{ fecha }} - Hora: {{ hora }}</p>'
            ),
            'body_text': (
                'Error durante un análisis\n'
                'El análisis de {{ dominio }} falló.\n'
                'Detalle: {{ error }}'
            ),
        },
        'vulnerability_critical': {
            'subject': 'CRÍTICO: Vulnerabilidad detectada en {{ dominio }}',
            'body_html': (
                '<h3>Vulnerabilidad crítica detectada</h3>'
                '<p>Se detectó la vulnerabilidad <strong>{{ vulnerabilidad }}</strong> en '
                '<strong>{{ dominio }}</strong>.</p>'
                '<p>Riesgo actual: {{ riesgo_actual }}</p>'
                '<p>{% if url %}<a href="{{ url }}">Ver detalle</a>{% endif %}</p>'
            ),
            'body_text': (
                'CRÍTICO: Vulnerabilidad detectada en {{ dominio }}\n'
                'Se detectó la vulnerabilidad {{ vulnerabilidad }} en {{ dominio }}.\n'
                'Riesgo actual: {{ riesgo_actual }}'
            ),
        },
    }

    for item in events:
        event = NotificationEvent.objects.create(**item)
        tpl = defaults.get(item['code'], {})
        EmailTemplate.objects.create(
            event=event,
            subject=tpl.get('subject', item['name']),
            body_html=tpl.get(
                'body_html',
                f'<h3>{item["name"]}</h3><p>{{{{ nombre_empresa }}}} - {{{{ fecha }}}} {{{{ hora }}}}</p>',
            ),
            body_text=tpl.get(
                'body_text',
                f'{item["name"]}\n{{{{ nombre_empresa }}}} - {{{{ fecha }}}} {{{{ hora }}}}',
            ),
        )


def remove_events(apps, schema_editor):
    NotificationEvent = apps.get_model('mailer', 'NotificationEvent')
    NotificationEvent.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('mailer', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_events, remove_events),
    ]
