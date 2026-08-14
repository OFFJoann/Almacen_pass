import io
import json
import os
import tempfile

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import logout
from django.core import management
from django.shortcuts import render, redirect, get_object_or_404
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q, Avg
from django.db import transaction
from django.http import HttpResponse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_POST
from datetime import timedelta
from apps.users.models import User, Group, LoginHistory, ActiveSession
from apps.passwords.models import PasswordEntry, Vault, Share
from apps.secrets.models import Secret
from apps.audit.models import AuditLog


@login_required
def dashboard(request):
    if not request.user.can_manage_users():
        raise PermissionDenied
    now = timezone.now()
    last_24h = now - timedelta(hours=24)
    last_7d = now - timedelta(days=7)
    last_30d = now - timedelta(days=30)

    from apps.passwords.risk import compute_user_risk, risk_label, robustness_label
    from apps.users.geo import get_country_for_ip

    group_id = request.GET.get('group', '').strip()
    selected_group = None
    users_qs = User.objects.all()
    if group_id:
        selected_group = get_object_or_404(Group, pk=group_id)
        users_qs = users_qs.filter(custom_groups=selected_group)

    total_users = users_qs.count()
    active_users = users_qs.filter(is_active=True).count()
    blocked_users = users_qs.filter(is_active=False).count()

    passwords_qs = PasswordEntry.objects.filter(
        is_deleted=False, is_obsolete=False, vault__user__in=users_qs
    )
    total_passwords = passwords_qs.count()
    total_vaults = Vault.objects.filter(user__in=users_qs).count()
    total_groups = Group.objects.count()
    total_shares = Share.objects.filter(is_revoked=False, entry__vault__user__in=users_qs).count()

    recent_logins = LoginHistory.objects.filter(
        user__in=users_qs, success=True, login_at__gte=last_24h
    ).count()
    failed_logins = LoginHistory.objects.filter(
        user__in=users_qs, success=False, login_at__gte=last_24h
    ).count()
    total_failed_logins = LoginHistory.objects.filter(
        user__in=users_qs, success=False
    ).count()

    active_sessions = ActiveSession.objects.filter(
        user__in=users_qs, expires_at__gt=now
    ).count()

    logins_last_7d = LoginHistory.objects.filter(
        user__in=users_qs, success=True, login_at__gte=last_7d
    ).count()
    logins_last_30d = LoginHistory.objects.filter(
        user__in=users_qs, success=True, login_at__gte=last_30d
    ).count()

    users_with_mfa = users_qs.filter(mfa_enabled=True).count()

    total_audit_logs = AuditLog.objects.filter(user__in=users_qs).count()
    recent_audit_logs = AuditLog.objects.filter(user__in=users_qs, created_at__gte=last_24h)[:20]

    logins_today = LoginHistory.objects.filter(
        user__in=users_qs, success=True,
        login_at__gte=now.replace(hour=0, minute=0, second=0)
    ).count()

    weak_passwords_count = passwords_qs.filter(
        sensitivity__in=['low', 'medium']
    ).count()

    expired_passwords = passwords_qs.filter(expires_at__lt=now).count()

    total_users_all_time = users_qs.count()
    storage_stats = {
        'total_passwords': total_passwords,
        'total_vaults': total_vaults,
        'total_shares': total_shares,
        'total_groups': total_groups,
    }

    security_score = 0
    if total_users > 0:
        avg_score = users_qs.filter(is_active=True).aggregate(
            avg=Avg('security_score')
        )['avg'] or 0
        security_score = round(avg_score, 1)

    # --- Nuevas métricas: riesgo general agregado, darkweb, robustez, intentos con país ---
    user_risks = [compute_user_risk(u) for u in users_qs]
    risk_values = [r['total_risk_score'] for r in user_risks]
    robustness_values = [r['robustness_pct'] for r in user_risks]

    general_risk = round(sum(risk_values) / len(risk_values), 1) if risk_values else 0
    general_risk_label, general_risk_color = risk_label(general_risk)

    avg_robustness = round(sum(robustness_values) / len(robustness_values), 1) if robustness_values else 0
    avg_robustness_label, avg_robustness_color = robustness_label(avg_robustness)

    compromised_qs = passwords_qs.filter(is_compromised=True)
    darkweb_total = compromised_qs.count()
    darkweb_owners = list(
        compromised_qs.values('vault__user__email', 'vault__user__full_name')
        .annotate(count=Count('id')).order_by('-count')
    )
    darkweb_passwords = list(
        compromised_qs.select_related('vault__user')
        .order_by('-compromised_checked_at')[:20]
    )

    login_attempts = list(
        LoginHistory.objects.filter(user__in=users_qs)
        .select_related('user').order_by('-login_at')[:30]
    )
    for attempt in login_attempts:
        attempt.country = get_country_for_ip(attempt.ip_address)

    groups = Group.objects.all().order_by('name')

    context = {
        'total_users': total_users,
        'active_users': active_users,
        'blocked_users': blocked_users,
        'total_passwords': total_passwords,
        'total_shares': total_shares,
        'total_groups': total_groups,
        'recent_logins': recent_logins,
        'failed_logins_24h': failed_logins,
        'total_failed_logins': total_failed_logins,
        'active_sessions': active_sessions,
        'logins_last_7d': logins_last_7d,
        'logins_last_30d': logins_last_30d,
        'users_with_mfa': users_with_mfa,
        'mfa_percentage': round((users_with_mfa / total_users * 100) if total_users else 0, 1),
        'total_audit_logs': total_audit_logs,
        'recent_audit_logs': recent_audit_logs,
        'logins_today': logins_today,
        'weak_passwords_count': weak_passwords_count,
        'expired_passwords': expired_passwords,
        'total_users_all_time': total_users_all_time,
        'storage_stats': storage_stats,
        'security_score': security_score,
        'selected_group': selected_group,
        'groups': groups,
        'user_risks': user_risks,
        'general_risk': general_risk,
        'general_risk_label': general_risk_label,
        'general_risk_color': general_risk_color,
        'avg_robustness': avg_robustness,
        'avg_robustness_label': avg_robustness_label,
        'avg_robustness_color': avg_robustness_color,
        'darkweb_total': darkweb_total,
        'darkweb_owners': darkweb_owners,
        'darkweb_passwords': darkweb_passwords,
        'login_attempts': login_attempts,
    }

    return render(request, 'admin_dashboard/dashboard.html', context)


@login_required
def obsolete_records(request):
    if not request.user.can_manage_users():
        raise PermissionDenied

    owner_q = request.GET.get('user', '').strip()

    entries = PasswordEntry.objects.filter(is_obsolete=True)
    secrets = Secret.objects.filter(is_obsolete=True)
    if owner_q:
        owner_filter = Q(email__icontains=owner_q) | Q(full_name__icontains=owner_q)
        owner_ids = User.objects.filter(owner_filter).values_list('pk', flat=True)
        entries = entries.filter(vault__user_id__in=owner_ids)
        secrets = secrets.filter(user_id__in=owner_ids)

    entries = entries.select_related('vault__user', 'folder', 'category').order_by('-obsoleted_at')
    secrets = secrets.select_related('user').order_by('-obsoleted_at')

    return render(request, 'admin_dashboard/obsolete.html', {
        'entries': entries,
        'secrets': secrets,
        'owner_q': owner_q,
    })


@login_required
@require_POST
def obsolete_delete_password(request, pk):
    if not request.user.can_manage_users():
        raise PermissionDenied
    entry = get_object_or_404(PasswordEntry, pk=pk, is_obsolete=True)
    name = entry.name
    owner = entry.vault.user.email if entry.vault and entry.vault.user else ''
    entry.delete()
    AuditLog.objects.create(
        user=request.user,
        action='PASSWORD_DELETED',
        details=f'Admin deleted obsolete password: {name} (owner: {owner})',
        result='success',
        ip_address=request.META.get('REMOTE_ADDR', ''),
    )
    messages.success(request, _('Contraseña obsoleta eliminada permanentemente'))
    return redirect('admin_dashboard:obsolete')


@login_required
@require_POST
def obsolete_delete_secret(request, pk):
    if not request.user.can_manage_users():
        raise PermissionDenied
    secret = get_object_or_404(Secret, pk=pk, is_obsolete=True)
    name = secret.name
    owner = secret.user.email if secret.user else ''
    secret.delete()
    AuditLog.objects.create(
        user=request.user,
        action='PASSWORD_DELETED',
        details=f'Admin deleted obsolete secret: {name} (owner: {owner})',
        result='success',
        ip_address=request.META.get('REMOTE_ADDR', ''),
    )
    messages.success(request, _('Secreto obsoleto eliminado permanentemente'))
    return redirect('admin_dashboard:obsolete')


@login_required
def backup_page(request):
    if not request.user.can_manage_users():
        raise PermissionDenied
    return render(request, 'admin_dashboard/backup.html')


BACKUP_EXCLUDE_APPS = [
    'contenttypes',
    'auth.permission',
    'admin.logentry',
    'sessions',
    'axes',
]


@login_required
def backup_download(request):
    if not request.user.can_manage_users():
        raise PermissionDenied

    buf = io.StringIO()
    try:
        management.call_command(
            'dumpdata',
            exclude=BACKUP_EXCLUDE_APPS,
            format='json',
            stdout=buf,
            verbosity=0,
        )
    except Exception as exc:  # noqa: BLE001
        messages.error(request, _('Error al generar el backup: %s') % exc)
        return redirect('admin_dashboard:backup')

    filename = f'epm_backup_{timezone.now().strftime("%Y%m%d_%H%M%S")}.json'
    response = HttpResponse(buf.getvalue(), content_type='application/json')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    AuditLog.objects.create(
        user=request.user,
        action='DATABASE_BACKUP',
        details=f'Descargó un backup completo de la base de datos ({filename})',
        result='success',
        ip_address=request.META.get('REMOTE_ADDR', ''),
    )
    return response


@login_required
@require_POST
def backup_restore(request):
    if not request.user.can_manage_users():
        raise PermissionDenied

    backup_file = request.FILES.get('backup_file')
    if not backup_file:
        messages.error(request, _('Debes seleccionar un archivo de backup para restaurar.'))
        return redirect('admin_dashboard:backup')

    if not backup_file.name.lower().endswith('.json'):
        messages.error(request, _('El archivo debe ser un backup JSON generado por este sistema.'))
        return redirect('admin_dashboard:backup')

    # Validar que el contenido sea un dumpdata JSON válido antes de tocar la base de datos.
    try:
        raw = backup_file.read()
        parsed = json.loads(raw.decode('utf-8'))
        if not isinstance(parsed, list):
            raise ValueError('El backup no tiene el formato esperado (lista de objetos).')
    except Exception as exc:  # noqa: BLE001
        messages.error(request, _('El archivo no es un backup válido: %s') % exc)
        return redirect('admin_dashboard:backup')

    fd, tmp_path = tempfile.mkstemp(suffix='.json', prefix='epm_restore_')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as fh:
            fh.write(raw.decode('utf-8'))

        AuditLog.objects.create(
            user=request.user,
            action='DATABASE_RESTORE',
            details='Inició la restauración de un backup completo de la base de datos',
            result='pending',
            ip_address=request.META.get('REMOTE_ADDR', ''),
        )

        with transaction.atomic():
            management.call_command('flush', interactive=False, verbosity=0)
            management.call_command('loaddata', tmp_path, verbosity=0, app_label=None)

        AuditLog.objects.create(
            user=request.user,
            action='DATABASE_RESTORE',
            details='Restauró un backup completo de la base de datos',
            result='success',
            ip_address=request.META.get('REMOTE_ADDR', ''),
        )
    except Exception as exc:  # noqa: BLE001
        AuditLog.objects.create(
            user=request.user,
            action='DATABASE_RESTORE',
            details=f'Falló la restauración del backup: {exc}',
            result='failure',
            ip_address=request.META.get('REMOTE_ADDR', ''),
        )
        messages.error(request, _('Error al restaurar el backup: %s') % exc)
        return redirect('admin_dashboard:backup')
    finally:
        os.unlink(tmp_path)

    # La restauración puede haber cambiado usuarios/sesiones: se cierra la sesión actual.
    logout(request)
    messages.success(request, _('Backup restaurado correctamente. Inicia sesión de nuevo.'))
    return redirect('authentication:login')
