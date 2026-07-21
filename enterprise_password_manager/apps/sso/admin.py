from django.contrib import admin
from .models import SSOConfiguration, SSOLog


@admin.register(SSOConfiguration)
class SSOConfigurationAdmin(admin.ModelAdmin):
    list_display = ['provider', 'tenant_id', 'client_id', 'is_active', 'created_at']
    list_filter = ['provider', 'is_active']
    search_fields = ['tenant_id', 'client_id']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('Proveedor', {'fields': ('provider',)}),
        ('Credenciales', {'fields': ('tenant_id', 'client_id', 'client_secret')}),
        ('URLs', {'fields': ('redirect_uri', 'logout_uri')}),
        ('Alcances', {'fields': ('scopes',)}),
        ('Configuración', {'fields': ('is_active', 'sync_groups', 'just_in_time_provisioning', 'allow_local_auth')}),
    )


@admin.register(SSOLog)
class SSOLogAdmin(admin.ModelAdmin):
    list_display = ['user_email', 'action', 'success', 'created_at']
    list_filter = ['action', 'success']
    search_fields = ['user_email']
    readonly_fields = ['created_at']
