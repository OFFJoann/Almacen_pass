from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.db.models import Q
from django.views.decorators.http import require_POST
from datetime import timedelta
from .models import Secret, SecretShare
from .forms import ApiKeyForm, SshKeyForm, CreditCardForm, CustomSecretForm, SecretShareForm
from apps.users.models import get_user_effective_policy
from apps.mailer.services import notify_event

FORM_MAP = {
    'api_key': ApiKeyForm,
    'ssh_key': SshKeyForm,
    'credit_card': CreditCardForm,
    'custom': CustomSecretForm,
}


@login_required
def secret_list(request):
    my_secrets = Secret.objects.filter(user=request.user, is_deleted=False, is_obsolete=False)

    user_group_ids = list(request.user.groups.values_list('pk', flat=True))
    shared_to_me = SecretShare.objects.filter(
        Q(is_revoked=False),
        Q(shared_with_user=request.user) | Q(shared_with_group__in=user_group_ids),
        secret__is_deleted=False,
        secret__is_obsolete=False,
    ).select_related('shared_by', 'secret')

    trash_count = Secret.objects.filter(user=request.user, is_deleted=True).count()
    return render(request, 'secrets/secret_list.html', {
        'secrets': my_secrets,
        'shared_to_me': shared_to_me,
        'trash_count': trash_count,
    })


@login_required
def secret_create(request, secret_type):
    if secret_type not in FORM_MAP:
        messages.error(request, _('Tipo de secreto inválido.'))
        return redirect('secrets:list')

    form_class = FORM_MAP[secret_type]

    if request.method == 'POST':
        form = form_class(request.POST, secret_type=secret_type)
        if form.is_valid():
            secret = form.save(commit=False)
            secret.user = request.user
            secret.save()
            messages.success(request, _('%(name)s creado exitosamente.') % {'name': secret.get_type_display()})
            return redirect('secrets:list')
    else:
        form = form_class(secret_type=secret_type)

    return render(request, 'secrets/secret_form.html', {
        'form': form,
        'secret_type': secret_type,
        'type_label': dict(Secret.TYPE_CHOICES).get(secret_type, ''),
    })


@login_required
def secret_edit(request, pk):
    secret = get_object_or_404(Secret, pk=pk, user=request.user, is_deleted=False, is_obsolete=False)
    form_class = FORM_MAP.get(secret.type)
    if not form_class:
        messages.error(request, _('Tipo de secreto inválido.'))
        return redirect('secrets:list')

    if request.method == 'POST':
        form = form_class(request.POST, secret_type=secret.type, instance=secret)
        if form.is_valid():
            form.save()
            messages.success(request, _('Secreto actualizado exitosamente.'))
            return redirect('secrets:list')
    else:
        data = secret.get_data()
        initial = {'notes': secret.get_notes()}
        if secret.type == 'api_key':
            initial.update({
                'provider': data.get('provider', ''),
                'api_key': data.get('api_key', ''),
                'endpoint_url': data.get('endpoint_url', ''),
            })
        elif secret.type == 'ssh_key':
            initial.update({
                'host': data.get('host', ''),
                'port': int(data.get('port', 22)),
                'username': data.get('username', ''),
                'private_key': data.get('private_key', ''),
                'public_key': data.get('public_key', ''),
                'passphrase': data.get('passphrase', ''),
            })
        elif secret.type == 'credit_card':
            initial.update({
                'card_number': data.get('card_number', ''),
                'card_holder': data.get('card_holder', ''),
                'expiry_month': data.get('expiry_month', ''),
                'expiry_year': data.get('expiry_year', ''),
                'cvv': data.get('cvv', ''),
                'brand': data.get('brand', ''),
            })
        elif secret.type == 'custom':
            fields_data = data.get('fields', [])
            lines = '\n'.join(f"{f['name']}={f['value']}" for f in fields_data)
            initial['custom_fields'] = lines

        form = form_class(secret_type=secret.type, instance=secret, initial=initial)

    return render(request, 'secrets/secret_form.html', {
        'form': form,
        'secret_type': secret.type,
        'type_label': dict(Secret.TYPE_CHOICES).get(secret.type, ''),
        'is_edit': True,
    })


@login_required
def secret_delete(request, pk):
    secret = get_object_or_404(Secret, pk=pk, user=request.user, is_deleted=False, is_obsolete=False)
    if request.method == 'POST':
        name = secret.name
        secret.is_deleted = True
        secret.deleted_at = timezone.now()
        secret.save()
        messages.success(request, _('Secreto "%(name)s" movido a la papelera.') % {'name': name})
        return redirect('secrets:list')
    return render(request, 'secrets/secret_confirm_delete.html', {
        'secret': secret,
    })


@login_required
def secret_restore(request, pk):
    secret = get_object_or_404(Secret, pk=pk, user=request.user, is_deleted=True)
    secret.is_deleted = False
    secret.deleted_at = None
    secret.save()
    messages.success(request, _('Secreto restaurado.'))
    return redirect('secrets:trash')


@login_required
def secret_permanent_delete(request, pk):
    secret = get_object_or_404(Secret, pk=pk, user=request.user, is_deleted=True)
    policy = get_user_effective_policy(request.user)
    retention = policy['trash_retention_days']
    if secret.deleted_at and timezone.now() - secret.deleted_at < timedelta(days=retention):
        days_left = retention - (timezone.now() - secret.deleted_at).days
        messages.error(request, _('Deben pasar %(days)d días en la papelera. Quedan %(left)s día(s).')
                         % {'days': retention, 'left': days_left})
        return redirect('secrets:trash')
    secret.delete()
    messages.success(request, _('Secreto eliminado permanentemente.'))
    return redirect('secrets:trash')


@login_required
def secret_trash(request):
    return redirect('passwords:trash')


@login_required
@require_POST
def secret_mark_obsolete(request, pk):
    secret = get_object_or_404(
        Secret, pk=pk, user=request.user,
        is_deleted=False, is_obsolete=False,
    )
    secret.is_obsolete = True
    secret.obsoleted_at = timezone.now()
    secret.save(update_fields=['is_obsolete', 'obsoleted_at'])

    from apps.audit.models import AuditLog
    AuditLog.objects.create(
        user=request.user,
        action='PASSWORD_EDITED',
        details=f'Marked secret as obsolete: {secret.name}',
        result='success',
        ip_address=request.META.get('REMOTE_ADDR', ''),
    )
    messages.success(request, _('Secreto marcado como obsoleto y movido al módulo de obsoletos'))
    return redirect('passwords:obsolete')


@login_required
def secret_detail(request, pk):
    secret = get_object_or_404(Secret, pk=pk, is_deleted=False, is_obsolete=False)
    is_owner = secret.user == request.user
    user_share = None
    if not is_owner:
        user_group_ids = list(request.user.groups.values_list('pk', flat=True))
        user_share = SecretShare.objects.filter(
            Q(secret=secret) & Q(is_revoked=False) &
            (Q(shared_with_user=request.user) | Q(shared_with_group__in=user_group_ids))
        ).first()
        if not user_share:
            from django.http import Http404
            raise Http404
    fields = secret.get_fields_display()
    notes = secret.get_notes()
    all_shares = SecretShare.objects.filter(secret=secret).select_related('shared_with_user', 'shared_with_group').order_by('-created_at')
    seen = set()
    shares = []
    for s in all_shares:
        key = ('user', s.shared_with_user_id) if s.shared_with_user else ('group', s.shared_with_group_id)
        if key not in seen:
            seen.add(key)
            shares.append(s)
    return render(request, 'secrets/secret_detail.html', {
        'secret': secret,
        'fields': fields,
        'notes': notes,
        'shares': shares,
        'is_owner': is_owner,
        'user_share': user_share,
    })


@login_required
def secret_share(request, pk):
    secret = get_object_or_404(Secret, pk=pk, user=request.user, is_deleted=False, is_obsolete=False)

    if request.method == 'POST':
        form = SecretShareForm(request.POST, user=request.user)
        if form.is_valid():
            target_user = form.cleaned_data.get('shared_with_user')
            target_group = form.cleaned_data.get('shared_with_group')
            permission = form.cleaned_data.get('permission')
            expires_at = form.cleaned_data.get('expires_at')

            existing = None
            if target_user:
                existing = SecretShare.objects.filter(secret=secret, is_revoked=False, shared_with_user=target_user).first()
            elif target_group:
                existing = SecretShare.objects.filter(secret=secret, is_revoked=False, shared_with_group=target_group).first()

            if existing:
                existing.permission = permission
                existing.expires_at = expires_at
                existing.save(update_fields=['permission', 'expires_at'])
                messages.success(request, _('Permiso actualizado exitosamente.'))
            else:
                share = form.save(commit=False)
                share.secret = secret
                share.shared_by = request.user
                share.save()

                target = share.shared_with_user.email if share.shared_with_user else share.shared_with_group.name
                extra_recipients = []
                if target_user and target_user.email:
                    extra_recipients.append(target_user.email)
                elif target_group:
                    extra_recipients = [
                        u.email for u in target_group.members.filter(is_active=True) if u.email
                    ]
                notify_event('secret_shared', {
                    'compartido_por': request.user.email,
                    'compartido_con': target,
                    'nombre_servicio': secret.name,
                }, extra_recipients=extra_recipients)
                messages.success(request, _('Secreto compartido exitosamente.'))
            return redirect('secrets:detail', pk=secret.pk)
    else:
        form = SecretShareForm(user=request.user)

    all_existing = SecretShare.objects.filter(secret=secret).select_related('shared_with_user', 'shared_with_group').order_by('-created_at')
    seen = set()
    existing_shares = []
    for s in all_existing:
        key = ('user', s.shared_with_user_id) if s.shared_with_user else ('group', s.shared_with_group_id)
        if key not in seen:
            seen.add(key)
            existing_shares.append(s)
    return render(request, 'secrets/share_form.html', {
        'form': form,
        'secret': secret,
        'existing_shares': existing_shares,
    })


@login_required
@require_POST
def secret_revoke_share(request, share_id):
    share = get_object_or_404(SecretShare, pk=share_id, secret__user=request.user)
    target = share.shared_with_user.email if share.shared_with_user else share.shared_with_group.name
    share.revoke()
    notify_event('share_revoked', {
        'usuario': request.user.email,
        'compartido_con': target,
        'nombre_servicio': share.secret.name,
    })
    messages.success(request, _('Compartición revocada.'))
    return redirect('secrets:detail', pk=share.secret.pk)


@login_required
@require_POST
def secret_update_share_permission(request, share_id):
    share = get_object_or_404(SecretShare, pk=share_id, secret__user=request.user)
    new_permission = request.POST.get('permission')
    if new_permission in dict(SecretShare.PERMISSION_CHOICES):
        share.update_permission(new_permission)
        messages.success(request, _('Permiso actualizado.'))
    return redirect(request.META.get('HTTP_REFERER', 'secrets:list'))
