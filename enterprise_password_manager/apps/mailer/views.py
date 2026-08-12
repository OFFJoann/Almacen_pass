from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_POST

from .forms import (
    SMTPSettingsForm, TestEmailForm, NotificationGroupForm,
    NotificationRecipientForm, EmailTemplateForm,
)
from .models import (
    SMTPSettings, NotificationGroup, NotificationRecipient,
    NotificationEvent, GroupNotificationEvent, EmailTemplate,
)
from .services import (
    get_smtp_settings, send_test_email, sample_context, render_string,
    get_smtp_backend,
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
def group_list(request):
    _require_superadmin(request)
    groups = NotificationGroup.objects.annotate(
        num_recipients=Count('recipients')
    )
    search = request.GET.get('search', '')
    if search:
        groups = groups.filter(name__icontains=search)
    return render(request, 'mailer/group_list.html', {
        'groups': groups,
        'active_tab': 'groups',
    })


@login_required
def group_create(request):
    _require_superadmin(request)
    if request.method == 'POST':
        form = NotificationGroupForm(request.POST)
        if form.is_valid():
            group = form.save(commit=False)
            group.created_by = request.user
            group.save()
            messages.success(request, _('Grupo de notificaciones creado.'))
            return redirect('mailer:group_detail', pk=group.pk)
    else:
        form = NotificationGroupForm()
    return render(request, 'mailer/group_form.html', {
        'form': form,
        'active_tab': 'groups',
    })


@login_required
def group_edit(request, pk):
    _require_superadmin(request)
    group = get_object_or_404(NotificationGroup, pk=pk)
    if request.method == 'POST':
        form = NotificationGroupForm(request.POST, instance=group)
        if form.is_valid():
            form.save()
            messages.success(request, _('Grupo actualizado.'))
            return redirect('mailer:group_detail', pk=group.pk)
    else:
        form = NotificationGroupForm(instance=group)
    return render(request, 'mailer/group_form.html', {
        'form': form,
        'group': group,
        'active_tab': 'groups',
    })


@login_required
def group_delete(request, pk):
    _require_superadmin(request)
    group = get_object_or_404(NotificationGroup, pk=pk)
    if request.method == 'POST':
        name = group.name
        group.delete()
        messages.success(request, _('Grupo "%(name)s" eliminado.') % {'name': name})
        return redirect('mailer:groups')
    return render(request, 'mailer/group_confirm_delete.html', {
        'group': group,
        'active_tab': 'groups',
    })


@login_required
def group_detail(request, pk):
    _require_superadmin(request)
    group = get_object_or_404(NotificationGroup, pk=pk)
    events = NotificationEvent.objects.filter(is_active=True).select_related('template')
    configs = {
        c.event_id: c for c in GroupNotificationEvent.objects.filter(group=group)
    }
    recipients = group.recipients.all()
    return render(request, 'mailer/group_detail.html', {
        'group': group,
        'events': events,
        'configs': configs,
        'recipients': recipients,
        'recipient_form': NotificationRecipientForm(),
        'active_tab': 'groups',
    })


@login_required
@require_POST
def group_recipient_add(request, pk):
    _require_superadmin(request)
    group = get_object_or_404(NotificationGroup, pk=pk)
    form = NotificationRecipientForm(request.POST)
    if form.is_valid():
        recipient, created = NotificationRecipient.objects.get_or_create(
            group=group,
            email=form.cleaned_data['email'].lower(),
            defaults={
                'name': form.cleaned_data.get('name', ''),
                'is_active': form.cleaned_data.get('is_active', True),
            },
        )
        if created:
            messages.success(request, _('Destinatario agregado.'))
        else:
            messages.warning(request, _('El destinatario ya existía en este grupo.'))
    else:
        messages.error(request, _('Correo inválido.'))
    return redirect('mailer:group_detail', pk=group.pk)


@login_required
@require_POST
def group_recipient_delete(request, pk, recipient_id):
    _require_superadmin(request)
    group = get_object_or_404(NotificationGroup, pk=pk)
    recipient = get_object_or_404(NotificationRecipient, pk=recipient_id, group=group)
    recipient.delete()
    messages.success(request, _('Destinatario eliminado.'))
    return redirect('mailer:group_detail', pk=group.pk)


@login_required
@require_POST
def group_event_toggle(request, pk, event_id):
    _require_superadmin(request)
    group = get_object_or_404(NotificationGroup, pk=pk)
    event = get_object_or_404(NotificationEvent, pk=event_id, is_active=True)
    config, created = GroupNotificationEvent.objects.get_or_create(
        group=group, event=event,
        defaults={'is_enabled': True},
    )
    if not created:
        config.is_enabled = not config.is_enabled
        config.save()
    state = config.is_enabled
    return JsonResponse({
        'success': True,
        'enabled': state,
        'label': _('Habilitado') if state else _('Deshabilitado'),
    })


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
