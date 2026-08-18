from django.contrib import admin

from .models import License, Installation


@admin.register(License)
class LicenseAdmin(admin.ModelAdmin):
    list_display = ('id', 'max_users', 'is_valid', 'expires_at', 'activated_at', 'error')
    readonly_fields = (
        'max_users', 'expires_at', 'installation_id', 'issued_at',
        'activated_at', 'last_checked_at', 'is_valid', 'error',
    )

    def has_add_permission(self, request):
        return not License.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Installation)
class InstallationAdmin(admin.ModelAdmin):
    list_display = ('id', 'installation_id', 'created_at')
    readonly_fields = ('installation_id', 'created_at')

    def has_add_permission(self, request):
        return not Installation.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
