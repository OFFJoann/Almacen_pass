from django.contrib import admin
from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['user', 'action', 'result', 'ip_address', 'created_at']
    list_filter = ['action', 'result']
    search_fields = ['user__email', 'details', 'ip_address']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return False
