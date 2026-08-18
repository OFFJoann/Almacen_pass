from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import ApiToken


@admin.register(ApiToken)
class ApiTokenAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'created_at', 'expires_at', 'is_active', 'last_used_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'user__email', 'key')
    raw_id_fields = ('user',)
    readonly_fields = ('key', 'created_at', 'last_used_at')

    fieldsets = (
        (None, {
            'fields': ('user', 'name', 'expires_at', 'is_active'),
        }),
        (_('Datos generados'), {
            'fields': ('key', 'created_at', 'last_used_at'),
        }),
    )

