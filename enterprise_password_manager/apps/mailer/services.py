import logging
from urllib.parse import urlparse

from django.core.mail import EmailMultiAlternatives
from django.core.mail.backends.smtp import EmailBackend
from django.template import Context, Template as DjangoTemplate
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger('apps')

BASE_CONTEXT_KEYS = [
    'nombre_empresa', 'dominio', 'riesgo_actual', 'riesgo_anterior',
    'usuario', 'invitado', 'invitado_por', 'compartido_por', 'compartido_con',
    'nombre_servicio', 'url', 'fecha', 'hora', 'ip', 'resultado', 'error',
    'vulnerabilidad', 'métrica', 'nuevo_estado',
]


def get_smtp_settings():
    from .models import SMTPSettings
    return SMTPSettings.objects.filter(pk=1).first()


def domain_from_url(url):
    if not url:
        return ''
    try:
        parsed = urlparse(url)
        if not parsed.netloc:
            parsed = urlparse('//' + url)
        return parsed.netloc
    except Exception:
        return ''


def get_smtp_backend(sm=None):
    from .models import SMTPSettings
    if sm is None:
        sm = get_smtp_settings()
    if sm is None or not sm.is_active or not sm.host:
        return None
    use_tls = sm.encryption == 'tls'
    use_ssl = sm.encryption == 'ssl'
    return EmailBackend(
        host=sm.host,
        port=sm.port,
        username=sm.username,
        password=sm.get_password(),
        use_tls=use_tls,
        use_ssl=use_ssl,
        timeout=sm.timeout,
        fail_silently=False,
    )


def base_context():
    sm = get_smtp_settings()
    now = timezone.localtime()
    company = sm.company_name if sm and sm.company_name else 'TICOlvidé'
    return {
        'nombre_empresa': company,
        'dominio': '',
        'riesgo_actual': '',
        'riesgo_anterior': '',
        'usuario': '',
        'invitado': '',
        'invitado_por': '',
        'compartido_por': '',
        'compartido_con': '',
        'nombre_servicio': '',
        'url': '',
        'fecha': now.strftime('%d/%m/%Y'),
        'hora': now.strftime('%H:%M'),
        'ip': '',
        'resultado': '',
        'error': '',
        'vulnerabilidad': '',
        'métrica': '',
        'nuevo_estado': '',
    }


def sample_context(event=None):
    from .models import NotificationEvent
    ctx = base_context()
    ctx.update({
        'dominio': 'ejemplo.com',
        'riesgo_actual': 'Crítico',
        'riesgo_anterior': 'Alto',
        'usuario': 'usuario@ejemplo.com',
        'invitado': 'nuevo@ejemplo.com',
        'invitado_por': 'admin@ejemplo.com',
        'compartido_por': 'propietario@ejemplo.com',
        'compartido_con': 'colaborador@ejemplo.com',
        'nombre_servicio': 'Cuenta principal',
        'url': 'https://ejemplo.com',
        'ip': '192.168.1.10',
        'resultado': 'Finalizado correctamente',
        'error': 'No se pudo conectar con el servidor',
        'vulnerabilidad': 'CVE-2026-0001',
        'métrica': '87%',
        'nuevo_estado': 'Habilitado',
    })
    variables = []
    if event is not None:
        variables = event.available_variables or []
    for v in variables:
        if v not in ctx:
            ctx[v] = f'valor-{v}'
    return ctx


def render_string(template_string, context):
    if not template_string:
        return ''
    try:
        tpl = DjangoTemplate(template_string)
        return tpl.render(Context(context))
    except Exception as exc:
        logger.warning('Error al renderizar plantilla de correo: %s', exc)
        return template_string


def render_event_email(event, context, extra_variables=None):
    from .models import EmailTemplate
    tpl, _ = EmailTemplate.objects.get_or_create(event=event)
    ctx = base_context()
    ctx.update(context or {})
    if extra_variables:
        ctx.update(extra_variables)
    subject = render_string(tpl.subject, ctx)
    body_html = render_string(tpl.body_html, ctx)
    body_text = render_string(tpl.body_text, ctx)
    return subject, body_html, body_text


def send_email(to, subject, body_html, body_text, sm=None, event=None, group=None, status='sent'):
    backend = get_smtp_backend(sm)
    if backend is None:
        logger.warning('SMTP no configurado o inactivo. No se envió correo a %s', to)
        from .models import EmailLog
        EmailLog.objects.create(
            event=event, group=group, recipient=to, subject=subject,
            status='failed', error=_('SMTP no configurado o inactivo'),
        )
        return False, _('SMTP no configurado o inactivo')

    sm = sm or get_smtp_settings()
    from_name = sm.from_name or sm.company_name or 'TICOlvidé'
    from_email = sm.from_email or sm.username
    if not from_email:
        from .models import EmailLog
        EmailLog.objects.create(
            event=event, group=group, recipient=to, subject=subject,
            status='failed', error=_('Falta el correo remitente'),
        )
        return False, _('Falta el correo remitente')

    sender = f'{from_name} <{from_email}>'
    try:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=body_text or body_html,
            from_email=sender,
            to=[to],
            connection=backend,
        )
        if body_html:
            msg.attach_alternative(body_html, 'text/html')
        msg.send()
        from .models import EmailLog
        EmailLog.objects.create(
            event=event, group=group, recipient=to, subject=subject, status=status,
        )
        return True, ''
    except Exception as exc:
        logger.exception('Error al enviar correo a %s', to)
        from .models import EmailLog
        EmailLog.objects.create(
            event=event, group=group, recipient=to, subject=subject,
            status='failed', error=str(exc),
        )
        return False, str(exc)


def collect_targets(event_code):
    from .models import NotificationEvent, GroupNotificationEvent, NotificationRecipient
    try:
        event = NotificationEvent.objects.get(code=event_code, is_active=True)
    except NotificationEvent.DoesNotExist:
        return event_code, None, []
    targets = []
    configs = GroupNotificationEvent.objects.filter(
        event=event, is_enabled=True, group__is_active=True
    ).select_related('group')
    for config in configs:
        recipients = NotificationRecipient.objects.filter(
            group=config.group, is_active=True
        )
        for recipient in recipients:
            targets.append((config.group, recipient))
    return event_code, event, targets


def notify_event(event_code, context=None, triggered_by=None):
    """Enviar notificaciones para un evento a todos los grupos habilitados."""
    event_code, event, targets = collect_targets(event_code)
    if event is None or not targets:
        return 0
    sent = 0
    ctx = context or {}
    for group, recipient in targets:
        subject, body_html, body_text = render_event_email(event, ctx)
        ok, error = send_email(
            recipient.email, subject, body_html, body_text,
            event=event, group=group,
        )
        if ok:
            sent += 1
    return sent


def send_test_email(to, context=None):
    from .models import NotificationEvent, EmailTemplate
    from django.utils.translation import gettext_lazy as _

    event, created = NotificationEvent.objects.get_or_create(
        code='test_email', defaults={
            'name': _('Correo de prueba'),
            'category': 'system',
            'icon': 'envelope',
            'description': _('Correo de validación de la configuración SMTP.'),
            'available_variables': BASE_CONTEXT_KEYS,
        },
    )
    if created:
        EmailTemplate.objects.create(
            event=event,
            subject=_('Correo de prueba TICOlvidé'),
            body_html=(
                '<h2>Configuración SMTP correcta</h2>'
                '<p>Hola {{ nombre_empresa }} ({{ usuario }}), este correo confirma que '
                'el servidor SMTP está configurado correctamente.</p>'
                '<p><strong>Fecha:</strong> {{ fecha }} - <strong>Hora:</strong> {{ hora }}</p>'
            ),
            body_text=_(
                'Configuración SMTP correcta.\nEste correo confirma que el servidor SMTP '
                'está configurado correctamente.\nFecha: {{ fecha }} - Hora: {{ hora }}'
            ),
        )
    sm = get_smtp_settings()
    ctx = base_context()
    ctx['usuario'] = to
    ctx.update(context or {})
    subject, body_html, body_text = render_event_email(event, ctx)
    ok, error = send_email(to, subject, body_html, body_text, sm=sm, event=event, status='test')
    return ok, error
