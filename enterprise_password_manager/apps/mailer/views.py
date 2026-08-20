from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_POST

from .forms import (
    SMTPSettingsForm, TestEmailForm, EmailTemplateForm,
)
from .models import (
    SMTPSettings, NotificationEvent, EmailTemplate,
)
from .services import (
    get_smtp_settings, send_test_email, send_event_test, sample_context,
    render_string, get_smtp_backend,
)


def _require_superadmin(request):
    if not request.user.is_authenticated or not request.user.is_superadmin():
        raise PermissionDenied


@login_required
def settings_view(request):
    _require_superadmin(request)
    smtp = get_smtp_settings()
    configured = smtp is not None and bool(smtp.host) and smtp.is_active

    if request.method == 'POST':
        form = SMTPSettingsForm(request.POST, instance=smtp)
        if form.is_valid():
            form.save()
            messages.success(request, _('Configuración SMTP guardada exitosamente'))
            return redirect('mailer:settings')
    else:
        form = SMTPSettingsForm(instance=smtp)

    smtp_error = None
    if configured and request.GET.get('check') == '1':
        try:
            backend = get_smtp_backend()
            backend.open()
            backend.close()
        except Exception as exc:
            smtp_error = str(exc)
        else:
            messages.success(request, _('La conexión con el servidor SMTP fue exitosa'))

    return render(request, 'mailer/settings.html', {
        'form': form,
        'test_form': TestEmailForm(),
        'smtp': smtp,
        'configured': configured,
        'smtp_error': smtp_error,
        'active_tab': 'settings',
    })


@login_required
@require_POST
def settings_send_test(request):
    _require_superadmin(request)
    form = TestEmailForm(request.POST)
    if not form.is_valid():
        messages.error(request, _('Ingresa un correo de destino válido.'))
        return redirect('mailer:settings')
    ok, error = send_test_email(form.cleaned_data['to_email'])
    if ok:
        messages.success(request, _('Correo de prueba enviado correctamente.'))
    else:
        messages.error(request, _('No se pudo enviar el correo de prueba: %(error)s') % {'error': error})
    return redirect('mailer:settings')


@login_required
def template_list(request):
    _require_superadmin(request)
    events = NotificationEvent.objects.filter(is_active=True).order_by('category', 'order', 'name')
    return render(request, 'mailer/template_list.html', {
        'events': events,
        'active_tab': 'templates',
    })


@login_required
def template_edit(request, code):
    _require_superadmin(request)
    event = get_object_or_404(NotificationEvent, code=code, is_active=True)
    template, _ = EmailTemplate.objects.get_or_create(event=event)
    if request.method == 'POST':
        form = EmailTemplateForm(request.POST, instance=template)
        if form.is_valid():
            form.save()
            messages.success(request, _('Plantilla guardada.'))
            return redirect('mailer:template_list')
    else:
        form = EmailTemplateForm(instance=template)
    return render(request, 'mailer/template_form.html', {
        'form': form,
        'event': event,
        'active_tab': 'templates',
    })


@login_required
@require_POST
def template_send_test(request):
    _require_superadmin(request)
    code = (request.POST.get('code') or '').strip()
    to_email = (request.POST.get('to_email') or '').strip()
    if not code or not to_email or '@' not in to_email:
        messages.error(request, _('Ingresa un correo de destino válido.'))
        return redirect('mailer:template_list')
    event = get_object_or_404(NotificationEvent, code=code, is_active=True)
    ok, error = send_event_test(code, to_email)
    if ok:
        messages.success(
            request,
            _('Prueba de la plantilla "%(name)s" enviada a %(email)s.')
            % {'name': event.name, 'email': to_email}
        )
    else:
        messages.error(
            request,
            _('No se pudo enviar la prueba: %(error)s') % {'error': error}
        )
    return redirect('mailer:template_list')


@login_required
@require_POST
def template_preview(request, code):
    _require_superadmin(request)
    event = get_object_or_404(NotificationEvent, code=code, is_active=True)
    template, _ = EmailTemplate.objects.get_or_create(event=event)
    form = EmailTemplateForm(request.POST, instance=template)
    form.is_valid()
    ctx = sample_context(event)
    subject = render_string(form.cleaned_data.get('subject', ''), ctx)
    body_html = render_string(form.cleaned_data.get('body_html', ''), ctx)
    return JsonResponse({'subject': subject, 'body_html': body_html})
