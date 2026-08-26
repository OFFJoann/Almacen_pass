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
from django.http import HttpResponse, JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_POST
from datetime import timedelta
from apps.users.models import User, Group, LoginHistory, ActiveSession
from apps.passwords.models import PasswordEntry, Vault, Share
from apps.secrets.models import Secret
from apps.audit.models import AuditLog
from apps.api_tokens.models import ApiToken
from apps.admin_dashboard.forms import ApiTokenForm
from django.conf import settings


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
@require_POST
def obsolete_restore_password(request, pk):
    if not request.user.can_manage_users():
        raise PermissionDenied
    entry = get_object_or_404(PasswordEntry, pk=pk, is_obsolete=True)
    name = entry.name
    owner = entry.vault.user.email if entry.vault and entry.vault.user else ''
    entry.is_obsolete = False
    entry.obsoleted_at = None
    entry.save(update_fields=['is_obsolete', 'obsoleted_at'])
    AuditLog.objects.create(
        user=request.user,
        action='PASSWORD_RESTORED',
        details=f'Admin restored obsolete password to owner vault: {name} (owner: {owner})',
        result='success',
        ip_address=request.META.get('REMOTE_ADDR', ''),
    )
    messages.success(request, _('Contraseña devuelta a la bóveda de su dueño'))
    return redirect('admin_dashboard:obsolete')


@login_required
@require_POST
def obsolete_restore_secret(request, pk):
    if not request.user.can_manage_users():
        raise PermissionDenied
    secret = get_object_or_404(Secret, pk=pk, is_obsolete=True)
    name = secret.name
    owner = secret.user.email if secret.user else ''
    secret.is_obsolete = False
    secret.obsoleted_at = None
    secret.save(update_fields=['is_obsolete', 'obsoleted_at'])
    AuditLog.objects.create(
        user=request.user,
        action='SECRET_RESTORED',
        details=f'Admin restored obsolete secret to owner vault: {name} (owner: {owner})',
        result='success',
        ip_address=request.META.get('REMOTE_ADDR', ''),
    )
    messages.success(request, _('Secreto devuelto a la bóveda de su dueño'))
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


@login_required
def api_tokens_view(request):
    if not request.user.can_manage_users():
        raise PermissionDenied

    new_key = None
    if request.method == 'POST' and request.POST.get('action') == 'create':
        form = ApiTokenForm(request.POST)
        if form.is_valid():
            owner = form.cleaned_data.get('user') or request.user
            token = ApiToken.objects.create(
                user=owner,
                name=form.cleaned_data['name'].strip(),
                expires_at=form.cleaned_data.get('expires_at'),
                is_active=True,
            )
            new_key = token.key
            AuditLog.objects.create(
                user=request.user,
                action='API_TOKEN_CREATED',
                details=f'Creó token de API "{token.name}" para {owner.email}',
                result='success',
                ip_address=request.META.get('REMOTE_ADDR', ''),
            )
            messages.success(request, _('Token de API creado correctamente.'))
        else:
            messages.error(request, _('Revisa los datos del formulario.'))
    else:
        form = ApiTokenForm()

    tokens = ApiToken.objects.select_related('user').all().order_by('-created_at')

    return render(request, 'admin_dashboard/api_tokens.html', {
        'form': form,
        'tokens': tokens,
        'new_key': new_key,
        'api_docs_url': getattr(settings, 'API_REPORTS_BASE_URL', 'http://127.0.0.1:8001') + '/docs',
        'api_openapi_url': getattr(settings, 'API_REPORTS_BASE_URL', 'http://127.0.0.1:8001') + '/openapi.json',
    })


@login_required
@require_POST
def api_token_revoke(request, pk):
    if not request.user.can_manage_users():
        raise PermissionDenied

    token = get_object_or_404(ApiToken, pk=pk)
    token.is_active = False
    token.save(update_fields=['is_active'])
    AuditLog.objects.create(
        user=request.user,
        action='API_TOKEN_REVOKED',
        details=f'Revocó token de API "{token.name}" de {token.user.email}',
        result='success',
        ip_address=request.META.get('REMOTE_ADDR', ''),
    )
    messages.success(request, _('Token de API revocado.'))
    return redirect('admin_dashboard:api_tokens')


API_ENDPOINT_DOCS = [
    {
        'method': 'GET',
        'path': '/api/v1/admin/overview',
        'summary': 'Resumen general de la empresa',
        'description': 'Métricas agregadas del estado de la organización: usuarios, contraseñas, secretos, MFA, riesgo, robustez y filtraciones.',
        'parameters': [
            {'name': 'group_id', 'in': 'query', 'required': False, 'description': 'Filtrar por un grupo específico.'},
        ],
        'returns': [
            'generated_at: fecha/hora de generación',
            'scope: "all" o nombre del grupo filtrado',
            'total_users / active_users / blocked_users',
            'total_passwords / total_vaults / total_secrets / total_shares / total_groups',
            'users_with_mfa / mfa_percentage',
            'recent_logins_24h / failed_logins_24h / active_sessions',
            'logins_last_7d / logins_last_30d / total_audit_logs',
            'weak_passwords_count / expired_passwords',
            'security_score (0-100)',
            'general_risk / general_risk_label / avg_robustness / avg_robustness_label',
            'darkweb_total: contraseñas detectadas en filtraciones',
        ],
    },
    {
        'method': 'GET',
        'path': '/api/v1/admin/users',
        'summary': 'Listado de usuarios con riesgo individual',
        'description': 'Devuelve los usuarios y, por cada uno, su riesgo calculado (entropía, duplicadas, comprometidas, robustez).',
        'parameters': [
            {'name': 'group_id', 'in': 'query', 'required': False, 'description': 'Filtrar por grupo.'},
            {'name': 'limit', 'in': 'query', 'required': False, 'description': 'Cantidad (1-1000, default 100).'},
            {'name': 'offset', 'in': 'query', 'required': False, 'description': 'Desplazamiento (default 0).'},
        ],
        'returns': [
            'Arreglo de usuarios con: id, email, full_name, role, is_active, mfa_enabled, security_score',
            'last_login, created_at, groups (nombres)',
            'total_entries, weak_passwords_count, compromised_count, has_duplicates',
            'avg_entropy, total_risk_score, robustness_pct',
        ],
    },
    {
        'method': 'GET',
        'path': '/api/v1/admin/users/{user_id}',
        'summary': 'Detalle de un usuario',
        'description': 'Igual que un elemento de /users pero para un usuario concreto.',
        'parameters': [
            {'name': 'user_id', 'in': 'path', 'required': True, 'description': 'UUID del usuario.'},
        ],
        'returns': [
            'id, email, full_name, role, is_active, mfa_enabled, security_score',
            'last_login, created_at, groups',
            'total_entries, weak_passwords_count, compromised_count, has_duplicates',
            'avg_entropy, total_risk_score, robustness_pct',
        ],
    },
    {
        'method': 'GET',
        'path': '/api/v1/admin/groups',
        'summary': 'Grupos y sus políticas',
        'description': 'Lista los grupos de la empresa con su configuración de políticas.',
        'parameters': [],
        'returns': [
            'Arreglo de grupos con: id, name, description',
            'min_password_length, trash_retention_days, session_days, allow_export',
            'member_count',
        ],
    },
    {
        'method': 'GET',
        'path': '/api/v1/admin/risk',
        'summary': 'Riesgo agregado de la empresa',
        'description': 'Riesgo general y conteos de usuarios en situación de riesgo.',
        'parameters': [
            {'name': 'group_id', 'in': 'query', 'required': False, 'description': 'Filtrar por grupo.'},
        ],
        'returns': [
            'general_risk (0-100) / general_risk_label (Bajo/Medio/Alto/Crítico)',
            'avg_robustness / avg_robustness_label',
            'users_at_high_risk, users_with_duplicates, users_with_weak',
        ],
    },
    {
        'method': 'GET',
        'path': '/api/v1/admin/darkweb',
        'summary': 'Contraseñas en filtraciones (dark web)',
        'description': 'Contraseñas marcadas como comprometidas, con su propietario.',
        'parameters': [
            {'name': 'group_id', 'in': 'query', 'required': False, 'description': 'Filtrar por grupo.'},
            {'name': 'limit', 'in': 'query', 'required': False, 'description': 'Cantidad (1-500, default 50).'},
        ],
        'returns': [
            'Arreglo con: id, name, owner_email, owner_name',
            'compromised_count, compromised_checked_at',
        ],
    },
    {
        'method': 'GET',
        'path': '/api/v1/admin/audit',
        'summary': 'Registro de auditoría',
        'description': 'Acciones de auditoría de la empresa (quién hizo qué, resultado e IP).',
        'parameters': [
            {'name': 'user_id', 'in': 'query', 'required': False, 'description': 'Filtrar por usuario.'},
            {'name': 'action', 'in': 'query', 'required': False, 'description': 'Tipo de acción, p.ej. PASSWORD_CREATED.'},
            {'name': 'limit', 'in': 'query', 'required': False, 'description': 'Cantidad (1-1000, default 100).'},
            {'name': 'offset', 'in': 'query', 'required': False, 'description': 'Desplazamiento (default 0).'},
        ],
        'returns': [
            'Arreglo con: id, user_email, action, details, result',
            'created_at, ip_address',
        ],
    },
    {
        'method': 'GET',
        'path': '/api/v1/admin/login-attempts',
        'summary': 'Intentos de inicio de sesión',
        'description': 'Historial de intentos de login con geolocalización por IP y motivo de fallo.',
        'parameters': [
            {'name': 'user_id', 'in': 'query', 'required': False, 'description': 'Filtrar por usuario.'},
            {'name': 'success', 'in': 'query', 'required': False, 'description': 'true=exitosos, false=fallidos.'},
            {'name': 'days', 'in': 'query', 'required': False, 'description': 'Ventana en días (1-365, default 30).'},
            {'name': 'limit', 'in': 'query', 'required': False, 'description': 'Cantidad (1-1000, default 100).'},
        ],
        'returns': [
            'Arreglo con: id, user_email, success, ip_address, country',
            'login_at, failure_reason',
        ],
    },
    {
        'method': 'GET',
        'path': '/api/v1/admin/storage',
        'summary': 'Estadísticas de almacenamiento',
        'description': 'Conteos de contraseñas, bóvedas, secretos, compartidos y grupos.',
        'parameters': [
            {'name': 'group_id', 'in': 'query', 'required': False, 'description': 'Filtrar por grupo.'},
        ],
        'returns': [
            'total_passwords, total_vaults, total_secrets, total_shares, total_groups',
        ],
    },
    {
        'method': 'GET',
        'path': '/api/v1/admin/obsolete',
        'summary': 'Registros obsoletos',
        'description': 'Contraseñas y secretos de origen desconocido marcados como obsoletos.',
        'parameters': [
            {'name': 'kind', 'in': 'query', 'required': False, 'description': 'passwords | secrets | all (default all).'},
            {'name': 'owner', 'in': 'query', 'required': False, 'description': 'Filtrar por email o nombre del propietario.'},
            {'name': 'limit', 'in': 'query', 'required': False, 'description': 'Cantidad (1-1000, default 200).'},
        ],
        'returns': [
            'Arreglo con: id, kind (password|secret), name, owner_email, obsoleted_at',
        ],
    },
]


@login_required
def api_docs_view(request):
    if not request.user.can_manage_users():
        raise PermissionDenied

    auth_token = None
    if request.user.is_superadmin:
        auto, _ = ApiToken.objects.get_or_create(
            user=request.user,
            name='Sesión automática (documentación)',
            defaults={'is_active': True},
        )
        auth_token = auto.key

    base = getattr(settings, 'API_REPORTS_BASE_URL', 'http://127.0.0.1:8001')
    return render(request, 'admin_dashboard/api_docs.html', {
        'api_base_url': base,
        'auth_token': auth_token,
        'operations': API_ENDPOINT_DOCS,
    })
