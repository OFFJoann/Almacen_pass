from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from .models import User, Group, GroupMembership, LoginHistory, ActiveSession
from .admin_forms import VaultTransferForm
from .tasks import do_transfer


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['email', 'full_name', 'is_active', 'is_staff', 'security_score', 'mfa_enabled', 'created_at']
    list_filter = ['is_active', 'is_staff', 'is_superuser', 'mfa_enabled']
    search_fields = ['email', 'full_name']
    ordering = ['-created_at']
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        (_('Información personal'), {'fields': ('full_name', 'phone', 'avatar')}),
        (_('Permisos'), {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        (_('Seguridad'), {'fields': ('security_score', 'mfa_enabled', 'mfa_secret', 'force_password_change')}),
        (_('Fechas importantes'), {'fields': ('last_login', 'last_activity', 'created_at', 'updated_at')}),
    )
    readonly_fields = ['created_at', 'updated_at', 'last_login', 'security_score']
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'full_name', 'password1', 'password2'),
        }),
    )

    def get_actions(self, request):
        actions = super().get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        actions['transfer_and_delete_selected'] = (
            type(self).transfer_and_delete_selected,
            'transfer_and_delete_selected',
            _('Eliminar usuarios seleccionados (transferir bóveda)'),
        )
        return actions

    def delete_view(self, request, object_id, extra_context=None):
        try:
            obj = self.get_object(request, object_id)
        except self.model.DoesNotExist:
            obj = None

        if not obj:
            return self._get_obj_does_not_exist_redirect(request, self.model._meta, object_id)

        if request.method == 'POST':
            form = VaultTransferForm(request.POST)
            if form.is_valid():
                target_user = form.cleaned_data['target_user']

                if target_user == obj:
                    messages.error(request, _('No puedes transferir la bóveda al mismo usuario.'))
                    return self.delete_view_get(request, obj, form)

                do_transfer(
                    source_user_id=str(obj.pk),
                    target_user_id=str(target_user.pk),
                    admin_email=request.user.email,
                )

                User.objects.filter(pk=obj.pk).delete()
                self.message_user(
                    request,
                    _('Bóveda de %(source)s transferida a %(target)s y usuario eliminado.')
                    % {'source': obj, 'target': target_user.email},
                )
                return HttpResponseRedirect(reverse('admin:users_user_changelist'))
            else:
                return self.delete_view_get(request, obj, form)
        else:
            return self.delete_view_get(request, obj)

    def delete_view_get(self, request, obj, form=None):
        if form is None:
            form = VaultTransferForm()

        entry_count = 0
        try:
            entry_count = obj.vault.entries.count()
        except Exception:
            pass

        context = {
            **self.admin_site.each_context(request),
            'title': _('¿Está seguro de eliminar a %(name)s?') % {'name': obj},
            'object_name': str(obj),
            'object': obj,
            'opts': self.model._meta,
            'app_label': self.model._meta.app_label,
            'preserved_filters': self.get_preserved_filters(request),
            'has_delete_permission': self.has_delete_permission(request, obj),
            'form': form,
            'entry_count': entry_count,
            'media': self.media,
        }
        return render(request, 'admin/users/user/delete_confirmation.html', context)

    def transfer_and_delete_selected(self, request, queryset):
        if 'target_user' in request.POST:
            form = VaultTransferForm(request.POST)
            if form.is_valid():
                target_user = form.cleaned_data['target_user']
                total_entries = 0
                count = 0
                for obj in queryset:
                    if obj == target_user:
                        continue
                    try:
                        total_entries += obj.vault.entries.count()
                    except Exception:
                        pass
                    do_transfer(str(obj.pk), str(target_user.pk), request.user.email)
                    User.objects.filter(pk=obj.pk).delete()
                    count += 1
                self.message_user(
                    request,
                    _('%(count)s usuario(s) eliminado(s). Bóvedas transferidas a %(target)s (%(entries)s contraseñas).')
                    % {'count': count, 'target': target_user.email, 'entries': total_entries},
                )
                return HttpResponseRedirect(reverse('admin:users_user_changelist'))
            else:
                return self._transfer_selected_get(request, queryset, form)
        else:
            return self._transfer_selected_get(request, queryset)

    def _transfer_selected_get(self, request, queryset, form=None):
        if form is None:
            form = VaultTransferForm()
        total_entries = 0
        for obj in queryset:
            try:
                total_entries += obj.vault.entries.count()
            except Exception:
                pass
        context = {
            **self.admin_site.each_context(request),
            'title': _('Transferir bóvedas antes de eliminar'),
            'queryset': queryset,
            'opts': self.model._meta,
            'app_label': self.model._meta.app_label,
            'form': form,
            'total_entries': total_entries,
            'media': self.media,
        }
        return render(request, 'admin/users/user/transfer_selected_confirmation.html', context)


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ['name', 'created_by', 'member_count', 'created_at']
    search_fields = ['name']
    readonly_fields = ['created_at']

    def member_count(self, obj):
        return obj.members.count()
    member_count.short_description = _('Miembros')


@admin.register(GroupMembership)
class GroupMembershipAdmin(admin.ModelAdmin):
    list_display = ['user', 'group', 'role', 'joined_at']
    list_filter = ['role']
    search_fields = ['user__email', 'group__name']


@admin.register(LoginHistory)
class LoginHistoryAdmin(admin.ModelAdmin):
    list_display = ['user', 'ip_address', 'browser', 'success', 'login_at']
    list_filter = ['success']
    search_fields = ['user__email', 'ip_address']
    readonly_fields = ['login_at']


@admin.register(ActiveSession)
class ActiveSessionAdmin(admin.ModelAdmin):
    list_display = ['user', 'ip_address', 'browser', 'last_activity', 'is_trusted']
    list_filter = ['is_trusted', 'is_mfa_verified']
    search_fields = ['user__email']
