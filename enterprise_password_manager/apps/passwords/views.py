import json
import csv
import io
from collections import Counter
from datetime import timedelta
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_POST
from django.db.models import Q, Count
from apps.secrets.models import Secret
from apps.notifications.models import Notification
from .models import PasswordEntry, Folder, Category, Tag, Vault, Share, ShareRequest, ShareAccessLog, PasswordHistory
from .forms import (PasswordEntryForm, FolderForm, CategoryForm, TagForm,
                     ShareForm, ShareRequestForm, ImportForm, ExportForm)
from .encryption import generate_password, generate_passphrase, calculate_entropy, password_strength, strength_percentage, check_hibp
from apps.mailer.services import notify_event, domain_from_url


@login_required
def vault_view(request):
    vault, created = Vault.objects.get_or_create(user=request.user)
    folders = Folder.objects.filter(user=request.user)
    categories = Category.objects.filter(user=request.user)
    tags = Tag.objects.filter(user=request.user)

    entries = PasswordEntry.objects.filter(
        vault=vault, is_deleted=False, is_obsolete=False
    ).select_related('folder', 'category').prefetch_related('tags')

    folder_id = request.GET.get('folder')
    category_id = request.GET.get('category')
    tag_id = request.GET.get('tag')
    search = request.GET.get('search', '')
    sensitivity = request.GET.get('sensitivity')
    favorite = request.GET.get('favorite')

    if folder_id:
        entries = entries.filter(folder_id=folder_id)
    if category_id:
        entries = entries.filter(category_id=category_id)
    if tag_id:
        entries = entries.filter(tags__id=tag_id)
    if search:
        entries = entries.filter(name__icontains=search)
    if sensitivity:
        entries = entries.filter(sensitivity=sensitivity)
    if favorite:
        entries = entries.filter(is_favorite=True)

    for entry in entries:
        raw = entry.get_password()
        entry.strength_info = password_strength(raw) if raw else None

    shared_with_me = Share.objects.filter(
        Q(shared_with_user=request.user) | Q(shared_with_group__members=request.user),
        is_revoked=False,
        entry__is_deleted=False,
        entry__is_obsolete=False,
    ).filter(
        Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())
    ).select_related('entry', 'shared_by')

    return render(request, 'passwords/vault.html', {
        'vault': vault,
        'folders': folders,
        'categories': categories,
        'tags': tags,
        'entries': entries,
        'shared_entries': shared_with_me,
        'active_folder': folder_id,
        'active_category': category_id,
        'active_tag': tag_id,
        'search': search,
        'active_sensitivity': sensitivity,
        'favorite_filter': favorite,
    })


@login_required
def entry_create(request):
    vault, created = Vault.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        form = PasswordEntryForm(request.POST, user=request.user)
        if form.is_valid():
            entry = form.save(commit=False)
            entry.vault = vault
            entry.set_username(form.cleaned_data.get('username', ''))
            entry.set_password(form.cleaned_data.get('password', ''))
            entry.set_notes(form.cleaned_data.get('notes', ''))
            pwd = form.cleaned_data.get('password', '')
            if pwd:
                count = check_hibp(pwd)
                entry.is_compromised = count > 0
                entry.compromised_count = count
                entry.compromised_checked_at = timezone.now()
            entry.save()
            form.save_m2m()

            from apps.audit.models import AuditLog
            AuditLog.objects.create(
                user=request.user,
                action='PASSWORD_CREATED',
                details=f'Created password: {entry.name}',
                result='success',
                ip_address=request.META.get('REMOTE_ADDR', ''),
            )

            notify_event('password_created', {
                'usuario': request.user.email,
                'nombre_servicio': entry.name,
                'dominio': domain_from_url(entry.url),
                'url': entry.url or '/',
                'riesgo_actual': entry.get_sensitivity_display(),
            })
            if entry.is_compromised:
                notify_event('password_compromised', {
                    'usuario': request.user.email,
                    'nombre_servicio': entry.name,
                    'dominio': domain_from_url(entry.url),
                    'url': entry.url or '/',
                    'riesgo_actual': entry.get_sensitivity_display(),
                })

            if entry.is_compromised:
                messages.warning(request, _('Esta contraseña ha sido expuesta en filtraciones de datos. Se recomienda cambiarla.'))
            messages.success(request, _('Contraseña creada exitosamente'))
            return redirect('passwords:vault')
    else:
        form = PasswordEntryForm(user=request.user)
        initial = {}
        folder_id = request.GET.get('folder')
        category_id = request.GET.get('category')
        if folder_id:
            initial['folder'] = folder_id
        if category_id:
            initial['category'] = category_id
        form.initial = initial

    return render(request, 'passwords/entry_form.html', {
        'form': form,
        'title': _('Nueva Contraseña'),
    })


@login_required
def entry_edit(request, pk):
    entry = get_object_or_404(
        PasswordEntry.objects.filter(is_deleted=False, is_obsolete=False).filter(
            Q(vault__user=request.user) |
            Q(shares__shared_with_user=request.user, shares__is_revoked=False) |
            Q(shares__shared_with_group__members=request.user, shares__is_revoked=False)
        ).distinct(),
        pk=pk
    )

    is_owner = PasswordEntry.objects.filter(pk=entry.pk, vault__user=request.user).exists()
    if not is_owner:
        can_edit = Share.objects.filter(
            entry=entry, is_revoked=False, permission='write'
        ).filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())
        ).filter(
            Q(shared_with_user=request.user) | Q(shared_with_group__members=request.user)
        ).exists()
        if not can_edit:
            raise PermissionDenied(_('No tienes permiso para editar esta contraseña.'))

    if request.method == 'POST':
        form = PasswordEntryForm(request.POST, instance=entry, user=request.user)
        if form.is_valid():
            old_expires_at = entry.expires_at
            entry = form.save(commit=False)
            changes = []

            old_password = entry.get_password()
            new_password = form.cleaned_data.get('password', '')
            if new_password and old_password != new_password:
                changes.append('Contraseña')

            old_username = entry.get_username()
            new_username = form.cleaned_data.get('username', '')
            if old_username != new_username:
                changes.append('Usuario')

            old_notes = entry.get_notes()
            new_notes = form.cleaned_data.get('notes', '')
            if old_notes != new_notes:
                changes.append('Notas')

            if changes:
                PasswordHistory.objects.create(
                    entry=entry,
                    password_encrypted=entry.password_encrypted,
                    password_nonce=entry.password_nonce,
                    password_salt=entry.password_salt,
                    changed_by=request.user,
                    changes_summary=', '.join(changes),
                )
                if 'Contraseña' in changes:
                    entry.set_password(new_password)
                if 'Usuario' in changes:
                    entry.set_username(new_username)
                if 'Notas' in changes:
                    entry.set_notes(new_notes)
                entry.version += 1
            if old_expires_at != entry.expires_at:
                entry.expiry_notified_at = None
            pwd_to_check = new_password if 'Contraseña' in changes else None
            if pwd_to_check:
                count = check_hibp(pwd_to_check)
                entry.is_compromised = count > 0
                entry.compromised_count = count
                entry.compromised_checked_at = timezone.now()
            entry.save()
            form.save_m2m()

            from apps.audit.models import AuditLog
            AuditLog.objects.create(
                user=request.user,
                action='PASSWORD_EDITED',
                details=f'Edited password: {entry.name}',
                result='success',
                ip_address=request.META.get('REMOTE_ADDR', ''),
            )

            notify_event('password_modified', {
                'usuario': request.user.email,
                'nombre_servicio': entry.name,
                'dominio': domain_from_url(entry.url),
                'url': entry.url or '/',
            })

            messages.success(request, _('Contraseña actualizada exitosamente'))
            return redirect('passwords:vault')
    else:
        form = PasswordEntryForm(instance=entry, user=request.user)
        form.initial.update({
            'username': entry.get_username(),
            'password': entry.get_password(),
            'notes': entry.get_notes(),
        })

    return render(request, 'passwords/entry_form.html', {
        'form': form,
        'title': _('Editar Contraseña'),
        'entry': entry,
    })


@login_required
def entry_detail(request, pk):
    entry = get_object_or_404(
        PasswordEntry.objects.filter(is_deleted=False, is_obsolete=False).filter(
            Q(vault__user=request.user) |
            Q(shares__shared_with_user=request.user, shares__is_revoked=False) |
            Q(shares__shared_with_group__members=request.user, shares__is_revoked=False)
        ).distinct(),
        pk=pk
    )

    share = Share.objects.filter(
        entry=entry, is_revoked=False
    ).filter(
        Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())
    ).filter(
        Q(shared_with_user=request.user) | Q(shared_with_group__members=request.user)
    ).first()

    entry.last_accessed = timezone.now()
    entry.access_count += 1
    entry.save(update_fields=['last_accessed', 'access_count'])

    if share:
        ShareAccessLog.objects.create(
            share=share, user=request.user, action='view',
            ip_address=request.META.get('REMOTE_ADDR', ''),
        )

    all_shares = Share.objects.filter(entry=entry).select_related('shared_with_user', 'shared_with_group').order_by('-created_at')
    seen = set()
    shares = []
    for s in all_shares:
        key = ('user', s.shared_with_user_id) if s.shared_with_user else ('group', s.shared_with_group_id)
        if key not in seen:
            seen.add(key)
            shares.append(s)
    password_history = PasswordHistory.objects.filter(entry=entry)[:10]

    raw_password = entry.get_password()
    strength = password_strength(raw_password)
    pct = strength_percentage(strength['entropy'])

    is_owner = PasswordEntry.objects.filter(pk=entry.pk, vault__user=request.user).exists()

    pending_share_requests = []
    if is_owner:
        pending_share_requests = ShareRequest.objects.filter(
            entry=entry, status='pending'
        ).select_related('requested_by', 'target_user')

    return render(request, 'passwords/entry_detail.html', {
        'entry': entry,
        'username': entry.get_username(),
        'password': raw_password,
        'notes': entry.get_notes(),
        'shares': shares,
        'user_share': share,
        'is_owner': is_owner,
        'pending_share_requests': pending_share_requests,
        'password_history': password_history,
        'password_strength': strength,
        'strength_pct': pct,
    })


@login_required
def entry_delete(request, pk):
    entry = get_object_or_404(PasswordEntry, pk=pk, vault__user=request.user, is_deleted=False, is_obsolete=False)
    if request.method == 'POST':
        entry.is_deleted = True
        entry.deleted_at = timezone.now()
        entry.save()

        from apps.audit.models import AuditLog
        AuditLog.objects.create(
            user=request.user,
            action='PASSWORD_DELETED',
            details=f'Deleted password: {entry.name}',
            result='success',
            ip_address=request.META.get('REMOTE_ADDR', ''),
        )

        notify_event('password_deleted', {
            'usuario': request.user.email,
            'nombre_servicio': entry.name,
            'dominio': domain_from_url(entry.url),
        })

        messages.success(request, _('Contraseña movida a la papelera'))
    return redirect('passwords:vault')


@login_required
def entry_restore(request, pk):
    entry = get_object_or_404(PasswordEntry, pk=pk, vault__user=request.user, is_deleted=True)
    entry.is_deleted = False
    entry.deleted_at = None
    entry.save()
    messages.success(request, _('Contraseña restaurada'))
    return redirect('passwords:trash')


@login_required
def entry_permanent_delete(request, pk):
    from apps.users.models import get_user_effective_policy
    policy = get_user_effective_policy(request.user)
    retention = policy['trash_retention_days']

    entry = get_object_or_404(PasswordEntry, pk=pk, vault__user=request.user, is_deleted=True)
    if entry.deleted_at and timezone.now() - entry.deleted_at < timedelta(days=retention):
        days_left = retention - (timezone.now() - entry.deleted_at).days
        messages.error(request, _(f'Deben pasar %(days)d días en la papelera antes de eliminar permanentemente. Quedan %(left)s día(s).')
                         % {'days': retention, 'left': days_left})
        return redirect('passwords:trash')
    entry.delete()
    messages.success(request, _('Contraseña eliminada permanentemente'))
    return redirect('passwords:trash')


@login_required
def trash_view(request):
    from apps.users.models import get_user_effective_policy
    from apps.secrets.models import Secret
    policy = get_user_effective_policy(request.user)
    retention = policy['trash_retention_days']

    vault, created = Vault.objects.get_or_create(user=request.user)
    deleted_entries = PasswordEntry.objects.filter(
        vault=vault, is_deleted=True
    )
    deleted_secrets = Secret.objects.filter(
        user=request.user, is_deleted=True
    )
    now = timezone.now()
    for entry in deleted_entries:
        if entry.deleted_at:
            elapsed = now - entry.deleted_at
            entry.days_remaining = max(0, retention - elapsed.days)
            entry.can_permanently_delete = elapsed.days >= retention
        else:
            entry.days_remaining = retention
            entry.can_permanently_delete = False
    for secret in deleted_secrets:
        if secret.deleted_at:
            elapsed = now - secret.deleted_at
            secret.days_remaining = max(0, retention - elapsed.days)
            secret.can_permanently_delete = elapsed.days >= retention
        else:
            secret.days_remaining = retention
            secret.can_permanently_delete = False
    return render(request, 'passwords/trash.html', {
        'entries': deleted_entries,
        'secrets': deleted_secrets,
        'retention_days': retention,
    })


@login_required
def empty_trash(request):
    from apps.users.models import get_user_effective_policy
    from apps.secrets.models import Secret
    policy = get_user_effective_policy(request.user)
    retention = policy['trash_retention_days']

    vault, created = Vault.objects.get_or_create(user=request.user)
    cutoff = timezone.now() - timedelta(days=retention)
    deletable_entries = PasswordEntry.objects.filter(vault=vault, is_deleted=True, deleted_at__lte=cutoff)
    deletable_secrets = Secret.objects.filter(user=request.user, is_deleted=True, deleted_at__lte=cutoff)
    count = deletable_entries.count() + deletable_secrets.count()
    deletable_entries.delete()
    deletable_secrets.delete()
    messages.success(request, _(f'Papelera vaciada: {count} elemento(s) eliminado(s) permanentemente (los más recientes deben esperar %(days)d días).')
                     % {'days': retention})
    return redirect('passwords:trash')


@login_required
def obsolete_view(request):
    from apps.secrets.models import Secret
    vault, created = Vault.objects.get_or_create(user=request.user)
    entries = PasswordEntry.objects.filter(
        vault=vault, is_obsolete=True
    ).select_related('folder', 'category').prefetch_related('tags').order_by('-obsoleted_at')
    secrets = Secret.objects.filter(
        user=request.user, is_obsolete=True
    ).order_by('-obsoleted_at')
    return render(request, 'passwords/obsolete.html', {
        'entries': entries,
        'secrets': secrets,
    })


@login_required
@require_POST
def entry_mark_obsolete(request, pk):
    entry = get_object_or_404(
        PasswordEntry, pk=pk, vault__user=request.user,
        is_deleted=False, is_obsolete=False,
    )
    entry.is_obsolete = True
    entry.obsoleted_at = timezone.now()
    entry.save(update_fields=['is_obsolete', 'obsoleted_at'])

    from apps.audit.models import AuditLog
    AuditLog.objects.create(
        user=request.user,
        action='PASSWORD_EDITED',
        details=f'Marked password as obsolete: {entry.name}',
        result='success',
        ip_address=request.META.get('REMOTE_ADDR', ''),
    )
    messages.success(request, _('Contraseña marcada como obsoleta y movida al módulo de obsoletos'))
    return redirect('passwords:obsolete')


@login_required
def toggle_favorite(request, pk):
    entry = get_object_or_404(PasswordEntry, pk=pk, vault__user=request.user)
    entry.is_favorite = not entry.is_favorite
    entry.save(update_fields=['is_favorite'])
    return JsonResponse({'is_favorite': entry.is_favorite})


@login_required
def entry_share(request, pk):
    entry = get_object_or_404(
        PasswordEntry.objects.filter(is_deleted=False, is_obsolete=False).filter(
            Q(vault__user=request.user) |
            Q(shares__shared_with_user=request.user, shares__is_revoked=False) |
            Q(shares__shared_with_group__members=request.user, shares__is_revoked=False)
        ).distinct(),
        pk=pk
    )

    is_owner = PasswordEntry.objects.filter(pk=entry.pk, vault__user=request.user).exists()
    if not is_owner:
        can_reshare = Share.objects.filter(
            entry=entry, is_revoked=False, permission='reshare'
        ).filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())
        ).filter(
            Q(shared_with_user=request.user) | Q(shared_with_group__members=request.user)
        ).exists()
        if not can_reshare:
            raise PermissionDenied(_('No tienes permiso para re-compartir esta contraseña.'))

    if not is_owner:
        if request.method == 'POST':
            form = ShareRequestForm(request.POST, user=request.user, entry=entry)
            if form.is_valid():
                share_request = ShareRequest.objects.create(
                    entry=entry,
                    requested_by=request.user,
                    target_user=form.cleaned_data['target_user'],
                    requested_days=form.cleaned_data['requested_days'],
                )
                owner = entry.vault.user
                duration = _('sin expiración') if not share_request.requested_days else f'{share_request.requested_days} día(s)'
                Notification.objects.create(
                    user=owner,
                    title=_('Solicitud de re-compartición'),
                    message=_('%(requester)s solicita compartir «%(entry)s» con %(target)s (duración: %(duration)s).')
                             % {'requester': request.user.full_name or request.user.email,
                                'entry': entry.name,
                                'target': share_request.target_user.email,
                                'duration': duration},
                    notification_type='info',
                    action_url=reverse('passwords:share_requests'),
                )
                from apps.audit.models import AuditLog
                AuditLog.objects.create(
                    user=request.user,
                    action='SHARE_REQUESTED',
                    details=f'Requested reshare: {entry.name} with {share_request.target_user.email} for {share_request.requested_days} days',
                    result='success',
                    ip_address=request.META.get('REMOTE_ADDR', ''),
                )
                messages.success(request, _('Se envió la solicitud de re-compartición al dueño del registro. Espera su aprobación.'))
                return redirect('passwords:detail', pk=entry.pk)
        else:
            form = ShareRequestForm(user=request.user, entry=entry)
        return render(request, 'passwords/share_request_form.html', {
            'form': form,
            'entry': entry,
        })

    if request.method == 'POST':
        form = ShareForm(request.POST, user=request.user)
        if form.is_valid():
            target_user = form.cleaned_data.get('shared_with_user')
            target_group = form.cleaned_data.get('shared_with_group')
            permission = form.cleaned_data.get('permission')
            expires_at = form.cleaned_data.get('expires_at')

            existing = None
            if target_user:
                existing = Share.objects.filter(entry=entry, is_revoked=False, shared_with_user=target_user).first()
            elif target_group:
                existing = Share.objects.filter(entry=entry, is_revoked=False, shared_with_group=target_group).first()

            if existing:
                existing.permission = permission
                existing.expires_at = expires_at
                existing.save(update_fields=['permission', 'expires_at'])
                messages.success(request, _('Permiso actualizado exitosamente.'))
            else:
                share = form.save(commit=False)
                share.entry = entry
                share.shared_by = request.user
                share.save()

                from apps.audit.models import AuditLog
                target = share.shared_with_user.email if share.shared_with_user else share.shared_with_group.name
                AuditLog.objects.create(
                    user=request.user,
                    action='PASSWORD_SHARED',
                    details=f'Shared password: {entry.name} with {target}',
                    result='success',
                    ip_address=request.META.get('REMOTE_ADDR', ''),
                )

                notify_event('password_shared', {
                    'compartido_por': request.user.email,
                    'compartido_con': target,
                    'nombre_servicio': entry.name,
                    'url': entry.url or '/',
                })
                messages.success(request, _('Contraseña compartida exitosamente'))

            return redirect('passwords:detail', pk=entry.pk)
    else:
        form = ShareForm(user=request.user)

    all_existing = Share.objects.filter(entry=entry).select_related('shared_with_user', 'shared_with_group').order_by('-created_at')
    seen = set()
    existing_shares = []
    for s in all_existing:
        key = ('user', s.shared_with_user_id) if s.shared_with_user else ('group', s.shared_with_group_id)
        if key not in seen:
            seen.add(key)
            existing_shares.append(s)
    return render(request, 'passwords/share_form.html', {
        'form': form,
        'entry': entry,
        'existing_shares': existing_shares,
    })


@login_required
@require_POST
def revoke_share(request, share_id):
    share = get_object_or_404(Share, pk=share_id, entry__vault__user=request.user)
    share.revoke()

    from apps.audit.models import AuditLog
    AuditLog.objects.create(
        user=request.user,
        action='SHARE_REVOKED',
        details=f'Revoked share: {share.entry.name}',
        result='success',
        ip_address=request.META.get('REMOTE_ADDR', ''),
    )

    target = share.shared_with_user.email if share.shared_with_user else share.shared_with_group.name
    notify_event('share_revoked', {
        'usuario': request.user.email,
        'compartido_con': target,
        'nombre_servicio': share.entry.name,
    })

    messages.success(request, _('Acceso revocado'))
    return redirect('passwords:detail', pk=share.entry.pk)


@login_required
@require_POST
def update_share_permission(request, share_id):
    share = get_object_or_404(Share, pk=share_id, entry__vault__user=request.user)
    new_permission = request.POST.get('permission')
    if new_permission in dict(Share.PERMISSION_CHOICES):
        share.update_permission(new_permission)
        messages.success(request, _('Permiso actualizado.'))
    return redirect(request.META.get('HTTP_REFERER', 'passwords:vault'))


@login_required
def share_requests_list(request):
    requests_qs = ShareRequest.objects.filter(
        entry__vault__user=request.user
    ).select_related('entry', 'requested_by', 'target_user')
    my_requests = ShareRequest.objects.filter(
        requested_by=request.user
    ).select_related('entry', 'target_user')
    return render(request, 'passwords/share_requests.html', {
        'pending_requests': requests_qs.filter(status='pending'),
        'responded_requests': requests_qs.exclude(status='pending'),
        'my_requests': my_requests,
    })


@login_required
@require_POST
def share_request_approve(request, request_id):
    share_request = get_object_or_404(
        ShareRequest, pk=request_id, entry__vault__user=request.user, status='pending'
    )
    entry = share_request.entry
    target = share_request.target_user
    now = timezone.now()
    if share_request.requested_days:
        expires_at = now + timezone.timedelta(days=share_request.requested_days)
    else:
        expires_at = None

    existing = Share.objects.filter(
        entry=entry, is_revoked=False, shared_with_user=target
    ).first()
    if existing:
        existing.permission = 'read'
        existing.expires_at = expires_at
        existing.save(update_fields=['permission', 'expires_at'])
    else:
        Share.objects.create(
            entry=entry,
            shared_by=request.user,
            shared_with_user=target,
            permission='read',
            expires_at=expires_at,
        )

    share_request.status = 'approved'
    share_request.responded_by = request.user
    share_request.responded_at = now
    share_request.save(update_fields=['status', 'responded_by', 'responded_at'])

    duration = _('ilimitada') if not share_request.requested_days else f'{share_request.requested_days} día(s)'
    Notification.objects.create(
        user=share_request.requested_by,
        title=_('Re-compartición aprobada'),
        message=_('Tu solicitud para compartir «%(entry)s» con %(target)s (duración: %(duration)s) fue aprobada.')
                 % {'entry': entry.name, 'target': target.email, 'duration': duration},
        notification_type='success',
        action_url=reverse('passwords:detail', kwargs={'pk': entry.pk}),
    )

    from apps.audit.models import AuditLog
    AuditLog.objects.create(
        user=request.user,
        action='SHARE_APPROVED',
        details=f'Approved reshare request: {entry.name} with {target.email} for {duration}',
        result='success',
        ip_address=request.META.get('REMOTE_ADDR', ''),
    )

    messages.success(request, _('Solicitud aprobada y contraseña compartida.'))
    return redirect('passwords:share_requests')


@login_required
@require_POST
def share_request_deny(request, request_id):
    share_request = get_object_or_404(
        ShareRequest, pk=request_id, entry__vault__user=request.user, status='pending'
    )
    share_request.status = 'denied'
    share_request.responded_by = request.user
    share_request.responded_at = timezone.now()
    share_request.save(update_fields=['status', 'responded_by', 'responded_at'])

    Notification.objects.create(
        user=share_request.requested_by,
        title=_('Re-compartición denegada'),
        message=_('Tu solicitud para compartir «%(entry)s» con %(target)s fue denegada.')
                 % {'entry': share_request.entry.name, 'target': share_request.target_user.email},
        notification_type='warning',
    )

    from apps.audit.models import AuditLog
    AuditLog.objects.create(
        user=request.user,
        action='SHARE_DENIED',
        details=f'Denied reshare request: {share_request.entry.name} with {share_request.target_user.email}',
        result='success',
        ip_address=request.META.get('REMOTE_ADDR', ''),
    )

    messages.success(request, _('Solicitud denegada.'))
    return redirect('passwords:share_requests')


@login_required
def password_generator(request):
    length = int(request.GET.get('length', 24))
    use_upper = request.GET.get('upper', 'true') == 'true'
    use_lower = request.GET.get('lower', 'true') == 'true'
    use_digits = request.GET.get('digits', 'true') == 'true'
    use_symbols = request.GET.get('symbols', 'true') == 'true'
    exclude_similar = request.GET.get('exclude_similar', 'false') == 'true'
    exclude_ambiguous = request.GET.get('exclude_ambiguous', 'false') == 'true'
    passphrase = request.GET.get('passphrase', 'false') == 'true'
    num_words = int(request.GET.get('num_words', 4))

    if passphrase:
        password = generate_passphrase(num_words)
    else:
        password = generate_password(length, use_upper, use_lower, use_digits,
                                      use_symbols, exclude_similar, exclude_ambiguous)

    entropy = calculate_entropy(password)

    return JsonResponse({
        'password': password,
        'entropy': entropy,
    })


@login_required
def import_passwords(request):
    if request.method == 'POST':
        form = ImportForm(request.POST, request.FILES)
        if form.is_valid():
            source = form.cleaned_data['source']
            file = request.FILES['file']
            vault, created = Vault.objects.get_or_create(user=request.user)
            imported_count = 0

            try:
                if source == 'csv':
                    decoded = file.read().decode('utf-8')
                    reader = csv.DictReader(io.StringIO(decoded))
                    for row in reader:
                        entry = PasswordEntry(vault=vault)
                        entry.name = row.get('name', row.get('Name', ''))
                        entry.set_username(row.get('username', row.get('Username', '')))
                        entry.set_password(row.get('password', row.get('Password', '')))
                        entry.set_notes(row.get('notes', row.get('Notes', '')))
                        entry.url = row.get('url', row.get('URL', ''))
                        entry.save()
                        imported_count += 1

                elif source == 'bitwarden':
                    data = json.loads(file.read().decode('utf-8'))
                    for item in data.get('items', []):
                        entry = PasswordEntry(vault=vault)
                        entry.name = item.get('name', '')
                        login_data = item.get('login', {})
                        entry.set_username(login_data.get('username', ''))
                        entry.set_password(login_data.get('password', ''))
                        entry.set_notes(item.get('notes', ''))
                        entry.url = login_data.get('uris', [{}])[0].get('uri', '') if login_data.get('uris') else ''
                        entry.save()
                        imported_count += 1

                elif source == 'keepass':
                    import xml.etree.ElementTree as ET
                    tree = ET.parse(file)
                    root = tree.getroot()
                    for entry_elem in root.findall('.//Entry'):
                        entry = PasswordEntry(vault=vault)
                        for string_elem in entry_elem.findall('String'):
                            key = string_elem.find('Key')
                            value = string_elem.find('Value')
                            if key is not None and value is not None:
                                k = key.text.lower() if key.text else ''
                                v = value.text or ''
                                if k == 'title':
                                    entry.name = v
                                elif k == 'username':
                                    entry.set_username(v)
                                elif k == 'password':
                                    entry.set_password(v)
                                elif k == 'notes':
                                    entry.set_notes(v)
                                elif k == 'url':
                                    entry.url = v
                        if entry.name:
                            entry.save()
                            imported_count += 1

                from apps.audit.models import AuditLog
                AuditLog.objects.create(
                    user=request.user,
                    action='PASSWORD_IMPORTED',
                    details=f'Imported {imported_count} passwords from {source}',
                    result='success',
                    ip_address=request.META.get('REMOTE_ADDR', ''),
                )

                messages.success(request, _(f'Se importaron {imported_count} contraseñas exitosamente'))
            except Exception as e:
                messages.error(request, _(f'Error al importar: {str(e)}'))

            return redirect('passwords:vault')
    else:
        form = ImportForm()

    return render(request, 'passwords/import.html', {'form': form})


@login_required
def export_passwords(request):
    vault, created = Vault.objects.get_or_create(user=request.user)
    entries = PasswordEntry.objects.filter(vault=vault, is_deleted=False, is_obsolete=False)

    export_format = request.GET.get('format', 'json')

    if export_format == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="passwords_export.csv"'
        writer = csv.writer(response)
        writer.writerow(['name', 'username', 'password', 'url', 'notes', 'folder', 'category'])

        for entry in entries:
            writer.writerow([
                entry.name,
                entry.get_username(),
                entry.get_password(),
                entry.url,
                entry.get_notes(),
                entry.folder.name if entry.folder else '',
                entry.category.name if entry.category else '',
            ])

        return response
    else:
        data = []
        for entry in entries:
            data.append({
                'name': entry.name,
                'username': entry.get_username(),
                'password': entry.get_password(),
                'url': entry.url,
                'notes': entry.get_notes(),
                'folder': entry.folder.name if entry.folder else '',
                'category': entry.category.name if entry.category else '',
                'sensitivity': entry.sensitivity,
                'created_at': entry.created_at.isoformat(),
            })

        response = HttpResponse(
            json.dumps(data, indent=2),
            content_type='application/json'
        )
        response['Content-Disposition'] = 'attachment; filename="passwords_export.json"'
        return response


@login_required
def folder_create(request):
    if request.method == 'POST':
        form = FolderForm(request.POST, user=request.user)
        if form.is_valid():
            folder = form.save(commit=False)
            folder.user = request.user
            folder.save()
            messages.success(request, _('Carpeta creada'))
            return redirect('passwords:vault')
    else:
        form = FolderForm(user=request.user)
    return render(request, 'passwords/folder_form.html', {'form': form})


@login_required
def category_create(request):
    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            category = form.save(commit=False)
            category.user = request.user
            category.save()
            messages.success(request, _('Categoría creada'))
            return redirect('passwords:vault')
    else:
        form = CategoryForm()
    return render(request, 'passwords/category_form.html', {'form': form})


@login_required
def folder_delete(request, pk):
    folder = get_object_or_404(Folder, pk=pk, user=request.user)
    children = folder.children.all()
    entry_count = folder.entries.count()
    if request.method == 'POST':
        name = folder.name
        folder.delete()
        messages.success(request, _('Carpeta "%(name)s" eliminada. Las contraseñas quedaron sin carpeta.')
                         % {'name': name})
        return redirect('passwords:vault')
    return render(request, 'passwords/folder_confirm_delete.html', {
        'folder': folder,
        'children': children,
        'entry_count': entry_count,
    })


@login_required
def category_delete(request, pk):
    category = get_object_or_404(Category, pk=pk, user=request.user)
    entry_count = category.entries.count()
    if request.method == 'POST':
        name = category.name
        category.delete()
        messages.success(request, _('Categoría "%(name)s" eliminada. Las contraseñas quedaron sin categoría.')
                         % {'name': name})
        return redirect('passwords:vault')
    return render(request, 'passwords/category_confirm_delete.html', {
        'category': category,
        'entry_count': entry_count,
    })


@login_required
def tag_create(request):
    if request.method == 'POST':
        form = TagForm(request.POST)
        if form.is_valid():
            tag = form.save(commit=False)
            tag.user = request.user
            tag.save()
            messages.success(request, _('Etiqueta creada'))
            return redirect('passwords:vault')
    else:
        form = TagForm()
    return render(request, 'passwords/tag_form.html', {'form': form})


@login_required
def totp_generate(request, pk):
    entry = get_object_or_404(
        PasswordEntry.objects.filter(is_deleted=False, is_obsolete=False).filter(
            Q(vault__user=request.user) |
            Q(shares__shared_with_user=request.user, shares__is_revoked=False) |
            Q(shares__shared_with_group__members=request.user, shares__is_revoked=False)
        ).distinct(),
        pk=pk
    )
    import pyotp

    secret = request.POST.get('secret', '').strip()
    if not secret:
        secret = pyotp.random_base32()

    entry.set_totp_secret(secret)
    entry.version += 1
    entry.save(update_fields=['totp_secret_encrypted', 'totp_secret_nonce', 'totp_secret_salt', 'version'])
    PasswordHistory.objects.create(
        entry=entry,
        password_encrypted=entry.password_encrypted,
        password_nonce=entry.password_nonce,
        password_salt=entry.password_salt,
        changed_by=request.user,
        changes_summary='2FA',
    )

    if request.headers.get('HX-Request'):
        return render(request, 'passwords/includes/totp_section.html', {'entry': entry})

    messages.success(request, _('2FA configurado correctamente'))
    return redirect('passwords:detail', pk=pk)


@login_required
def totp_remove(request, pk):
    entry = get_object_or_404(PasswordEntry, pk=pk, vault__user=request.user)
    entry.set_totp_secret('')
    entry.version += 1
    entry.save(update_fields=['totp_secret_encrypted', 'totp_secret_nonce', 'totp_secret_salt', 'version'])
    PasswordHistory.objects.create(
        entry=entry,
        password_encrypted=entry.password_encrypted,
        password_nonce=entry.password_nonce,
        password_salt=entry.password_salt,
        changed_by=request.user,
        changes_summary='2FA eliminado',
    )

    if request.headers.get('HX-Request'):
        return render(request, 'passwords/includes/totp_section.html', {'entry': entry})

    messages.success(request, _('2FA eliminado'))
    return redirect('passwords:detail', pk=pk)


@login_required
def totp_qr(request, pk):
    entry = get_object_or_404(
        PasswordEntry.objects.filter(is_deleted=False, is_obsolete=False).filter(
            Q(vault__user=request.user) |
            Q(shares__shared_with_user=request.user, shares__is_revoked=False) |
            Q(shares__shared_with_group__members=request.user, shares__is_revoked=False)
        ).distinct(),
        pk=pk
    )
    uri = entry.get_totp_uri()
    if not uri:
        return HttpResponse('Sin configuración 2FA', status=404)

    import qrcode
    img = qrcode.make(uri, box_size=6)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return HttpResponse(buf, content_type='image/png')


@login_required
def totp_current(request, pk):
    entry = get_object_or_404(
        PasswordEntry.objects.filter(is_deleted=False, is_obsolete=False).filter(
            Q(vault__user=request.user) |
            Q(shares__shared_with_user=request.user, shares__is_revoked=False) |
            Q(shares__shared_with_group__members=request.user, shares__is_revoked=False)
        ).distinct(),
        pk=pk
    )
    code = entry.get_current_totp()
    return JsonResponse({'code': code, 'has_totp': bool(code)})


@login_required
def entry_copy_data(request, pk):
    entry = get_object_or_404(
        PasswordEntry.objects.filter(is_deleted=False, is_obsolete=False).filter(
            Q(vault__user=request.user) |
            Q(shares__shared_with_user=request.user, shares__is_revoked=False) |
            Q(shares__shared_with_group__members=request.user, shares__is_revoked=False)
        ).distinct(),
        pk=pk
    )
    return JsonResponse({
        'username': entry.get_username() or '',
        'password': entry.get_password() or '',
        'url': entry.url or '',
        'totp': entry.get_current_totp() or '',
    })


@login_required
def password_history_restore(request, pk, hist_pk):
    entry = get_object_or_404(PasswordEntry, pk=pk, vault__user=request.user)
    history = get_object_or_404(PasswordHistory, pk=hist_pk, entry=entry)

    old_password = entry.get_password()
    if old_password:
        PasswordHistory.objects.create(
            entry=entry,
            password_encrypted=entry.password_encrypted,
            password_nonce=entry.password_nonce,
            password_salt=entry.password_salt,
            changed_by=request.user,
        )

    entry.password_encrypted = history.password_encrypted
    entry.password_nonce = history.password_nonce
    entry.password_salt = history.password_salt
    entry.version += 1
    entry.save(update_fields=['password_encrypted', 'password_nonce', 'password_salt', 'version'])

    from apps.audit.models import AuditLog
    AuditLog.objects.create(
        user=request.user,
        action='PASSWORD_RESTORED',
        details=f'Restored password version from {history.created_at.strftime("%Y-%m-%d %H:%M")} for: {entry.name}',
        result='success',
        ip_address=request.META.get('REMOTE_ADDR', ''),
    )

    messages.success(request, _('Versión anterior restaurada correctamente'))
    return redirect('passwords:detail', pk=pk)


@login_required
def user_dashboard(request):
    from apps.mailer.tasks import check_expired_passwords
    check_expired_passwords()

    vault, created = Vault.objects.get_or_create(user=request.user)
    now = timezone.now()

    entries = PasswordEntry.objects.filter(vault=vault, is_deleted=False, is_obsolete=False)
    total_entries = entries.count()
    expiring_soon = entries.filter(expires_at__lt=now).count()
    entries_expiring_30d = entries.filter(expires_at__gte=now, expires_at__lte=now + timedelta(days=30)).count()
    favorites = entries.filter(is_favorite=True).count()
    entries_with_totp = [e for e in entries if e.has_totp]
    totp_count = len(entries_with_totp)
    no_totp_entries = [e for e in entries if not e.has_totp]
    no_totp_count = len(no_totp_entries)

    category_counts = entries.values('category__name').annotate(count=Count('id')).order_by('-count')
    sensitivity_counts = entries.values('sensitivity').annotate(count=Count('id')).order_by('sensitivity')

    folders = entries.values('folder__name').annotate(count=Count('id')).order_by('-count')

    shares_given = Share.objects.filter(entry__vault=vault, is_revoked=False).count()
    shares_received = Share.objects.filter(
        Q(shared_with_user=request.user) | Q(shared_with_group__members=request.user),
        is_revoked=False
    ).distinct().count()

    shared_to_me = Share.objects.filter(
        Q(shared_with_user=request.user) | Q(shared_with_group__members=request.user),
        is_revoked=False,
        entry__is_deleted=False,
        entry__is_obsolete=False,
    ).distinct().select_related('entry', 'shared_by')[:10]

    weak_passwords_count = 0
    reused_passwords = []
    duplicate_groups = []

    plaintext_passwords = []
    for e in entries:
        try:
            pwd = e.get_password()
            if pwd:
                plaintext_passwords.append((e, pwd))
                strength = password_strength(pwd)
                if strength['level'] <= 2:
                    weak_passwords_count += 1
        except Exception:
            pass

    password_counter = Counter(pwd for _, pwd in plaintext_passwords)
    duplicates = {pwd: count for pwd, count in password_counter.items() if count > 1}

    if duplicates:
        dup_entries_by_pwd = {}
        for entry, pwd in plaintext_passwords:
            if pwd in duplicates:
                dup_entries_by_pwd.setdefault(pwd, []).append(entry)
        duplicate_groups = list(dup_entries_by_pwd.values())

    from apps.audit.models import AuditLog
    from apps.users.models import LoginHistory

    recent_activity = AuditLog.objects.filter(user=request.user)[:10]

    last_login = LoginHistory.objects.filter(user=request.user, success=True).order_by('-login_at').first()
    from apps.users.models import ActiveSession
    active_sessions_count = ActiveSession.objects.filter(user=request.user, expires_at__gt=now).count()

    all_passwords_count = len(plaintext_passwords)
    avg_entropy = 0
    if plaintext_passwords:
        avg_entropy = sum(calculate_entropy(pwd) for _, pwd in plaintext_passwords) / len(plaintext_passwords)

    compromised_count = entries.filter(is_compromised=True).count()

    score = 100
    score -= min(weak_passwords_count * 20, 50)
    score -= 25 if duplicates else 0
    score -= 25 if not request.user.mfa_enabled else 0
    score -= min(compromised_count * 15, 30)

    total_risk_score = max(0, min(100, score))

    if total_risk_score >= 80:
        risk_label = 'Bajo'
        risk_color = 'success'
    elif total_risk_score >= 60:
        risk_label = 'Moderado'
        risk_color = 'warning'
    elif total_risk_score >= 40:
        risk_label = 'Alto'
        risk_color = 'danger'
    else:
        risk_label = 'Crítico'
        risk_color = 'danger'

    max_entropy = 140
    robustness_pct = min(100, round((avg_entropy / max_entropy) * 100)) if total_entries > 0 else 0
    weak_ratio = weak_passwords_count / total_entries if total_entries > 0 else 0
    robustness_pct = max(0, robustness_pct - round(weak_ratio * 40))

    if robustness_pct >= 80:
        robustness_label = 'Muy Robusta'
        robustness_color = 'success'
    elif robustness_pct >= 60:
        robustness_label = 'Robusta'
        robustness_color = 'info'
    elif robustness_pct >= 40:
        robustness_label = 'Moderada'
        robustness_color = 'warning'
    elif robustness_pct >= 20:
        robustness_label = 'Débil'
        robustness_color = 'danger'
    else:
        robustness_label = 'Muy Débil'
        robustness_color = 'danger'

    secret_count = Secret.objects.filter(user=request.user, is_deleted=False).count()

    emergency_contact_required = request.user.can_manage_users() and not request.user.has_emergency_contact()
    emergency_contact_set = request.user.has_emergency_contact()

    old_entry = entries.filter(is_deleted=False).order_by('created_at').first()
    new_entry = entries.filter(is_deleted=False).order_by('-created_at').first()
    oldest_password_date = old_entry.created_at if old_entry else None
    newest_password_date = new_entry.created_at if new_entry else None

    context = {
        'total_entries': total_entries,
        'expiring_soon': expiring_soon,
        'entries_expiring_30d': entries_expiring_30d,
        'favorites': favorites,
        'totp_count': totp_count,
        'no_totp_count': no_totp_count,
        'no_totp_entries': no_totp_entries,
        'weak_passwords_count': weak_passwords_count,
        'duplicate_groups': duplicate_groups,
        'total_risk_score': round(total_risk_score, 1),
        'risk_label': risk_label,
        'risk_color': risk_color,
        'shares_given': shares_given,
        'shares_received': shares_received,
        'shared_to_me': shared_to_me,
        'category_counts': category_counts,
        'sensitivity_counts': sensitivity_counts,
        'folders': folders,
        'recent_activity': recent_activity,
        'last_login': last_login,
        'avg_entropy': round(avg_entropy, 1),
        'all_passwords_count': all_passwords_count,
        'oldest_password_date': oldest_password_date,
        'newest_password_date': newest_password_date,
        'mfa_enabled': request.user.mfa_enabled,
        'compromised_count': compromised_count,
        'robustness_pct': robustness_pct,
        'robustness_label': robustness_label,
        'robustness_color': robustness_color,
        'active_sessions_count': active_sessions_count,
        'secret_count': secret_count,
        'emergency_contact_required': emergency_contact_required,
        'emergency_contact_set': emergency_contact_set,
    }
    return render(request, 'passwords/user_dashboard.html', context)
