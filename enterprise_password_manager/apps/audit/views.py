from django.contrib.auth.mixins import PermissionRequiredMixin
from django.views.generic import ListView, DetailView
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from .models import AuditLog
from apps.users.models import LoginHistory, ActiveSession


class AuditLogListView(PermissionRequiredMixin, ListView):
    model = AuditLog
    template_name = 'audit/audit_log_list.html'
    context_object_name = 'logs'
    permission_required = 'audit.view_auditlog'
    paginate_by = 50

    def get_queryset(self):
        qs = AuditLog.objects.select_related('user')
        action = self.request.GET.get('action', '')
        user_id = self.request.GET.get('user', '')
        result = self.request.GET.get('result', '')
        date_from = self.request.GET.get('date_from', '')
        date_to = self.request.GET.get('date_to', '')
        if action:
            qs = qs.filter(action=action)
        if user_id:
            qs = qs.filter(user_id=user_id)
        if result:
            qs = qs.filter(result=result)
        if date_from:
            qs = qs.filter(created_at__gte=date_from)
        if date_to:
            qs = qs.filter(created_at__lte=date_to)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['action_choices'] = AuditLog.ACTION_CHOICES
        context['result_choices'] = AuditLog._meta.get_field('result').choices
        return context


class AuditLogDetailView(PermissionRequiredMixin, DetailView):
    model = AuditLog
    template_name = 'audit/audit_log_detail.html'
    permission_required = 'audit.view_auditlog'
    context_object_name = 'log'


@login_required
def user_activity_view(request, user_id):
    login_history = LoginHistory.objects.filter(user_id=user_id)[:50]
    audit_logs = AuditLog.objects.filter(user_id=user_id)[:50]
    active_sessions = ActiveSession.objects.filter(user_id=user_id)

    return render(request, 'audit/user_activity.html', {
        'login_history': login_history,
        'audit_logs': audit_logs,
        'active_sessions': active_sessions,
        'user_id': user_id,
    })


@login_required
def my_activity_view(request):
    login_history = LoginHistory.objects.filter(user=request.user)[:50]
    audit_logs = AuditLog.objects.filter(user=request.user)[:50]

    return render(request, 'audit/my_activity.html', {
        'login_history': login_history,
        'audit_logs': audit_logs,
    })
