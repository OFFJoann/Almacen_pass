from datetime import timedelta

from django.db.models import Count, Q, Avg
from django.utils import timezone

from apps.users.models import User, Group, LoginHistory, ActiveSession
from apps.passwords.models import PasswordEntry, Vault, Share
from apps.secrets.models import Secret
from apps.audit.models import AuditLog


def user_queryset(group_id=None):
    qs = User.objects.all()
    if group_id:
        qs = qs.filter(custom_groups__pk=group_id)
    return qs.distinct()


def password_queryset(users_qs):
    return PasswordEntry.objects.filter(
        is_deleted=False, is_obsolete=False, vault__user__in=users_qs
    )


def per_user_risk(user):
    from apps.passwords.risk import compute_user_risk
    return compute_user_risk(user)


def overview_data(group_id=None):
    now = timezone.now()
    last_24h = now - timedelta(hours=24)
    last_7d = now - timedelta(days=7)
    last_30d = now - timedelta(days=30)

    users_qs = user_queryset(group_id)
    total_users = users_qs.count()
    active_users = users_qs.filter(is_active=True).count()
    blocked_users = users_qs.filter(is_active=False).count()

    passwords_qs = password_queryset(users_qs)
    total_passwords = passwords_qs.count()
    total_vaults = Vault.objects.filter(user__in=users_qs).count()
    total_groups = Group.objects.count()
    total_secrets = Secret.objects.filter(user__in=users_qs, is_deleted=False, is_obsolete=False).count()
    total_shares = Share.objects.filter(
        is_revoked=False, entry__vault__user__in=users_qs
    ).count()

    recent_logins = LoginHistory.objects.filter(
        user__in=users_qs, success=True, login_at__gte=last_24h
    ).count()
    failed_logins = LoginHistory.objects.filter(
        user__in=users_qs, success=False, login_at__gte=last_24h
    ).count()
    active_sessions = ActiveSession.objects.filter(
        user__in=users_qs, expires_at__gt=now
    ).count()
    logins_7d = LoginHistory.objects.filter(
        user__in=users_qs, success=True, login_at__gte=last_7d
    ).count()
    logins_30d = LoginHistory.objects.filter(
        user__in=users_qs, success=True, login_at__gte=last_30d
    ).count()

    users_with_mfa = users_qs.filter(mfa_enabled=True).count()
    total_audit_logs = AuditLog.objects.filter(user__in=users_qs).count()
    weak_passwords_count = passwords_qs.filter(
        sensitivity__in=['low', 'medium']
    ).count()
    expired_passwords = passwords_qs.filter(expires_at__lt=now).count()

    security_score = 0.0
    if total_users > 0:
        avg = users_qs.filter(is_active=True).aggregate(avg=Avg('security_score'))['avg'] or 0
        security_score = round(avg, 1)

    from apps.passwords.risk import risk_label, robustness_label
    risks = [per_user_risk(u) for u in users_qs]
    risk_values = [r['total_risk_score'] for r in risks]
    robustness_values = [r['robustness_pct'] for r in risks]
    general_risk = round(sum(risk_values) / len(risk_values), 1) if risk_values else 0
    general_risk_label, _ = risk_label(general_risk)
    avg_robustness = round(sum(robustness_values) / len(robustness_values), 1) if robustness_values else 0
    avg_robustness_label, _ = robustness_label(avg_robustness)

    darkweb_total = passwords_qs.filter(is_compromised=True).count()

    scope = 'all'
    if group_id:
        g = Group.objects.filter(pk=group_id).first()
        scope = g.name if g else group_id

    return {
        'generated_at': now,
        'scope': scope,
        'total_users': total_users,
        'active_users': active_users,
        'blocked_users': blocked_users,
        'total_passwords': total_passwords,
        'total_vaults': total_vaults,
        'total_secrets': total_secrets,
        'total_shares': total_shares,
        'total_groups': total_groups,
        'users_with_mfa': users_with_mfa,
        'mfa_percentage': round((users_with_mfa / total_users * 100) if total_users else 0, 1),
        'recent_logins_24h': recent_logins,
        'failed_logins_24h': failed_logins,
        'active_sessions': active_sessions,
        'logins_last_7d': logins_7d,
        'logins_last_30d': logins_30d,
        'total_audit_logs': total_audit_logs,
        'weak_passwords_count': weak_passwords_count,
        'expired_passwords': expired_passwords,
        'security_score': security_score,
        'general_risk': general_risk,
        'general_risk_label': general_risk_label,
        'avg_robustness': avg_robustness,
        'avg_robustness_label': avg_robustness_label,
        'darkweb_total': darkweb_total,
    }


def list_users(group_id=None, limit=100, offset=0):
    qs = user_queryset(group_id).order_by('email')[offset:offset + limit]
    result = []
    for u in qs:
        r = per_user_risk(u)
        result.append({
            'id': str(u.id),
            'email': u.email,
            'full_name': u.full_name,
            'role': u.role,
            'is_active': u.is_active,
            'mfa_enabled': u.mfa_enabled,
            'security_score': u.security_score,
            
            'last_login': u.last_login,
            'created_at': u.created_at,
            'groups': list(u.custom_groups.values_list('name', flat=True)),
            'total_entries': r['total_entries'],
            'weak_passwords_count': r['weak_passwords_count'],
            'compromised_count': r['compromised_count'],
            'has_duplicates': r['has_duplicates'],
            'avg_entropy': r['avg_entropy'],
            'total_risk_score': r['total_risk_score'],
            'robustness_pct': r['robustness_pct'],
        })
    return result


def user_detail(user_id):
    u = User.objects.filter(pk=user_id).first()
    if not u:
        return None
    r = per_user_risk(u)
    return {
        'id': str(u.id),
        'email': u.email,
        'full_name': u.full_name,
        'role': u.role,
        'is_active': u.is_active,
        'mfa_enabled': u.mfa_enabled,
        'security_score': u.security_score,
        
        'last_login': u.last_login,
        'created_at': u.created_at,
        'groups': list(u.custom_groups.values_list('name', flat=True)),
        'total_entries': r['total_entries'],
        'weak_passwords_count': r['weak_passwords_count'],
        'compromised_count': r['compromised_count'],
        'has_duplicates': r['has_duplicates'],
        'avg_entropy': r['avg_entropy'],
        'total_risk_score': r['total_risk_score'],
        'robustness_pct': r['robustness_pct'],
    }


def list_groups():
    groups = Group.objects.annotate(member_count=Count('members', distinct=True)).order_by('name')
    return [{
        'id': str(g.id),
        'name': g.name,
        'description': g.description,
        'min_password_length': g.min_password_length,
        'trash_retention_days': g.trash_retention_days,
        'session_days': g.session_days,
        'allow_export': g.allow_export,
        'member_count': g.member_count,
    } for g in groups]


def risk_summary(group_id=None):
    from apps.passwords.risk import risk_label, robustness_label
    users_qs = user_queryset(group_id)
    risks = [per_user_risk(u) for u in users_qs]
    risk_values = [r['total_risk_score'] for r in risks]
    robustness_values = [r['robustness_pct'] for r in risks]
    general_risk = round(sum(risk_values) / len(risk_values), 1) if risk_values else 0
    general_risk_label, _ = risk_label(general_risk)
    avg_robustness = round(sum(robustness_values) / len(robustness_values), 1) if robustness_values else 0
    avg_robustness_label, _ = robustness_label(avg_robustness)
    return {
        'general_risk': general_risk,
        'general_risk_label': general_risk_label,
        'avg_robustness': avg_robustness,
        'avg_robustness_label': avg_robustness_label,
        'users_at_high_risk': sum(1 for v in risk_values if v <= 40),
        'users_with_duplicates': sum(1 for r in risks if r['has_duplicates']),
        'users_with_weak': sum(1 for r in risks if r['weak_passwords_count'] > 0),
    }


def darkweb_data(group_id=None, limit=50):
    passwords_qs = password_queryset(user_queryset(group_id)).filter(is_compromised=True)
    rows = list(
        passwords_qs.select_related('vault__user')
        .order_by('-compromised_checked_at')[:limit]
    )
    return [{
        'id': str(e.id),
        'name': e.name,
        'owner_email': e.vault.user.email if e.vault and e.vault.user else '',
        'owner_name': e.vault.user.full_name if e.vault and e.vault.user else '',
        'compromised_count': e.compromised_count,
        'compromised_checked_at': e.compromised_checked_at,
    } for e in rows]


def audit_data(user_id=None, action=None, limit=100, offset=0):
    qs = AuditLog.objects.all().select_related('user').order_by('-created_at')
    if user_id:
        qs = qs.filter(user__pk=user_id)
    if action:
        qs = qs.filter(action=action)
    for log in qs[offset:offset + limit]:
        yield {
            'id': str(log.id),
            'user_email': log.user.email if log.user else '',
            'action': log.action,
            'details': log.details,
            'result': log.result,
            'created_at': log.created_at,
            'ip_address': log.ip_address,
        }


def login_attempts_data(user_id=None, success=None, days=30, limit=100):
    now = timezone.now()
    since = now - timedelta(days=days)
    qs = LoginHistory.objects.filter(login_at__gte=since).select_related('user').order_by('-login_at')
    if user_id:
        qs = qs.filter(user__pk=user_id)
    if success is not None:
        qs = qs.filter(success=success)
    from apps.users.geo import get_country_for_ip
    rows = []
    for a in qs[:limit]:
        country = None
        try:
            geo = get_country_for_ip(a.ip_address)
            if isinstance(geo, dict):
                country = geo.get('country_name') or geo.get('country_code')
            else:
                country = geo
        except Exception:
            country = None
        rows.append({
            'id': str(a.id),
            'user_email': a.user.email if a.user else '',
            'success': a.success,
            'ip_address': a.ip_address,
            'country': country,
            'login_at': a.login_at,
            'failure_reason': a.failure_reason,
        })
    return rows


def storage_data(group_id=None):
    users_qs = user_queryset(group_id)
    passwords_qs = password_queryset(users_qs)
    return {
        'total_passwords': passwords_qs.count(),
        'total_vaults': Vault.objects.filter(user__in=users_qs).count(),
        'total_secrets': Secret.objects.filter(user__in=users_qs, is_deleted=False, is_obsolete=False).count(),
        'total_shares': Share.objects.filter(is_revoked=False, entry__vault__user__in=users_qs).count(),
        'total_groups': Group.objects.count(),
    }


def obsolete_data(kind='passwords', owner=None, limit=200):
    from apps.users.models import User as U
    rows = []
    if kind in ('passwords', 'all'):
        entries = PasswordEntry.objects.filter(is_obsolete=True).select_related('vault__user')
        if owner:
            ids = U.objects.filter(Q(email__icontains=owner) | Q(full_name__icontains=owner)).values_list('pk', flat=True)
            entries = entries.filter(vault__user_id__in=ids)
        for e in entries.order_by('-obsoleted_at')[:limit]:
            rows.append({
                'id': str(e.id),
                'kind': 'password',
                'name': e.name,
                'owner_email': e.vault.user.email if e.vault and e.vault.user else None,
                'obsoleted_at': e.obsoleted_at,
            })
    if kind in ('secrets', 'all'):
        secrets = Secret.objects.filter(is_obsolete=True).select_related('user')
        if owner:
            ids = U.objects.filter(Q(email__icontains=owner) | Q(full_name__icontains=owner)).values_list('pk', flat=True)
            secrets = secrets.filter(user_id__in=ids)
        for s in secrets.order_by('-obsoleted_at')[:limit]:
            rows.append({
                'id': str(s.id),
                'kind': 'secret',
                'name': s.name,
                'owner_email': s.user.email if s.user else None,
                'obsoleted_at': s.obsoleted_at,
            })
    return rows
