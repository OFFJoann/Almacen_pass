from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.db.models import Count, Q, Avg
from django.utils import timezone
from datetime import timedelta
from apps.users.models import User, Group, LoginHistory, ActiveSession
from apps.passwords.models import PasswordEntry, Vault, Share
from apps.audit.models import AuditLog


@staff_member_required
def dashboard(request):
    now = timezone.now()
    last_24h = now - timedelta(hours=24)
    last_7d = now - timedelta(days=7)
    last_30d = now - timedelta(days=30)

    total_users = User.objects.count()
    active_users = User.objects.filter(is_active=True).count()
    blocked_users = User.objects.filter(is_active=False).count()

    total_passwords = PasswordEntry.objects.filter(is_deleted=False).count()
    total_vaults = Vault.objects.count()
    total_groups = Group.objects.count()
    total_shares = Share.objects.filter(is_revoked=False).count()

    recent_logins = LoginHistory.objects.filter(
        success=True, login_at__gte=last_24h
    ).count()
    failed_logins = LoginHistory.objects.filter(
        success=False, login_at__gte=last_24h
    ).count()
    total_failed_logins = LoginHistory.objects.filter(success=False).count()

    active_sessions = ActiveSession.objects.filter(
        expires_at__gt=now
    ).count()

    logins_last_7d = LoginHistory.objects.filter(
        success=True, login_at__gte=last_7d
    ).count()
    logins_last_30d = LoginHistory.objects.filter(
        success=True, login_at__gte=last_30d
    ).count()

    users_with_mfa = User.objects.filter(mfa_enabled=True).count()

    total_audit_logs = AuditLog.objects.count()
    recent_audit_logs = AuditLog.objects.filter(created_at__gte=last_24h)[:20]

    passwords_by_sensitivity = PasswordEntry.objects.filter(
        is_deleted=False
    ).values('sensitivity').annotate(count=Count('id'))

    logins_today = LoginHistory.objects.filter(
        success=True, login_at__gte=now.replace(hour=0, minute=0, second=0)
    ).count()

    top_users = User.objects.annotate(
        password_count=Count('vault__entries', filter=Q(vault__entries__is_deleted=False))
    ).order_by('-password_count')[:10]

    weak_passwords_count = PasswordEntry.objects.filter(
        is_deleted=False, sensitivity__in=['low', 'medium']
    ).count()

    expired_passwords = PasswordEntry.objects.filter(
        is_deleted=False, expires_at__lt=now
    ).count()

    total_users_all_time = User.objects.count()
    storage_stats = {
        'total_passwords': total_passwords,
        'total_vaults': total_vaults,
        'total_shares': total_shares,
        'total_groups': total_groups,
    }

    security_score = 0
    if total_users > 0:
        avg_score = User.objects.filter(is_active=True).aggregate(
            avg=Avg('security_score')
        )['avg'] or 0
        security_score = round(avg_score, 1)

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
        'passwords_by_sensitivity': list(passwords_by_sensitivity),
        'logins_today': logins_today,
        'top_users': top_users,
        'weak_passwords_count': weak_passwords_count,
        'expired_passwords': expired_passwords,
        'total_users_all_time': total_users_all_time,
        'storage_stats': storage_stats,
        'security_score': security_score,
    }

    return render(request, 'admin_dashboard/dashboard.html', context)
