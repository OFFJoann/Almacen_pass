from django.contrib.auth.mixins import UserPassesTestMixin
from django.contrib.auth.decorators import login_required
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView, View
from django.urls import reverse_lazy
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext_lazy as _
from django.http import JsonResponse
from django.core.exceptions import PermissionDenied
from .models import User, Group, GroupMembership, LoginHistory, ActiveSession
from .forms import UserCreateForm, UserEditForm, GroupForm
from .admin_forms import VaultTransferForm
from .tasks import do_transfer
from apps.mailer.services import notify_event


class AdminUsersMixin(UserPassesTestMixin):
    """Allow access to superadmin and admin_usuarios."""
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.can_manage_users()


class SuperAdminMixin(UserPassesTestMixin):
    """Allow access only to superadmin."""
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_superadmin()


class UserListView(AdminUsersMixin, ListView):
    model = User
    template_name = 'users/user_list.html'
    context_object_name = 'users'
    paginate_by = 25

    def get_queryset(self):
        qs = super().get_queryset()
        search = self.request.GET.get('search', '')
        status = self.request.GET.get('status', '')
        if search:
            qs = qs.filter(email__icontains=search) | qs.filter(full_name__icontains=search)
        if status == 'active':
            qs = qs.filter(is_active=True)
        elif status == 'inactive':
            qs = qs.filter(is_active=False)
        return qs


class UserCreateView(AdminUsersMixin, CreateView):
    model = User
    form_class = UserCreateForm
    template_name = 'users/user_form.html'
    success_url = reverse_lazy('users:list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request_user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        response = super().form_valid(form)
        notify_event('user_created', {
            'usuario': form.instance.email,
            'invitado_por': self.request.user.email,
            'nuevo_estado': 'Activo',
        })
        messages.success(self.request, _('Usuario creado exitosamente'))
        return response


class UserUpdateView(AdminUsersMixin, UpdateView):
    model = User
    form_class = UserEditForm
    template_name = 'users/user_form.html'

    def get_success_url(self):
        return reverse_lazy('users:list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request_user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, _('Usuario actualizado exitosamente'))
        return super().form_valid(form)


class UserDeleteView(AdminUsersMixin, View):
    model = User

    def get_object(self):
        return get_object_or_404(User, pk=self.kwargs['pk'])

    def get(self, request, *args, **kwargs):
        obj = self.get_object()
        form = VaultTransferForm()
        entry_count = 0
        try:
            entry_count = obj.vault.entries.count()
        except Exception:
            pass
        return render(request, 'users/user_confirm_delete.html', {
            'object': obj,
            'form': form,
            'entry_count': entry_count,
        })

    def post(self, request, *args, **kwargs):
        obj = self.get_object()
        form = VaultTransferForm(request.POST)
        if form.is_valid():
            target_user = form.cleaned_data['target_user']
            if target_user == obj:
                messages.error(request, _('No puedes transferir la bóveda al mismo usuario.'))
                return render(request, 'users/user_confirm_delete.html', {
                    'object': obj, 'form': form,
                })
            do_transfer(str(obj.pk), str(target_user.pk), request.user.email)
            User.objects.filter(pk=obj.pk).delete()
            notify_event('user_deleted', {
                'usuario': obj.email,
                'invitado_por': request.user.email,
            })
            messages.success(
                request,
                _('Bóveda de %(source)s transferida a %(target)s y usuario eliminado.')
                % {'source': obj, 'target': target_user.email},
            )
            return redirect('users:list')
        return render(request, 'users/user_confirm_delete.html', {
            'object': obj, 'form': form, 'entry_count': 0,
        })


class UserDetailView(AdminUsersMixin, DetailView):
    model = User
    template_name = 'users/user_detail.html'
    context_object_name = 'user_obj'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['login_history'] = LoginHistory.objects.filter(user=self.object)[:10]
        context['active_sessions'] = ActiveSession.objects.filter(user=self.object)
        return context


@login_required
def user_toggle_active(request, pk):
    user = get_object_or_404(User, pk=pk)
    if request.user.can_manage_users():
        user.is_active = not user.is_active
        user.save()
        status = 'enabled' if user.is_active else 'disabled'
        messages.success(request, _(f'Usuario {status} exitosamente'))
    return redirect('users:list')


@login_required
def user_reset_password(request, pk):
    user = get_object_or_404(User, pk=pk)
    if not request.user.can_manage_users():
        messages.error(request, _('No tienes permiso para restablecer contraseñas.'))
        return redirect('users:list')
    if request.method == 'POST':
        password = request.POST.get('new_password', '').strip()
        confirm = request.POST.get('confirm_password', '').strip()
        if len(password) < 8:
            messages.error(request, _('La contraseña debe tener al menos 8 caracteres'))
        elif password != confirm:
            messages.error(request, _('Las contraseñas no coinciden'))
        else:
            user.set_password(password)
            user.force_password_change = True
            user.save()
            from apps.audit.models import AuditLog
            AuditLog.objects.create(
                user=request.user,
                action='PASSWORD_RESET_BY_ADMIN',
                details=f'Admin reset password for user: {user.email}',
                result='success',
                ip_address=request.META.get('REMOTE_ADDR', ''),
            )
            messages.success(request, _(f'Contraseña restablecida para {user.email}'))
            return redirect('users:list')
    return render(request, 'users/user_reset_password.html', {'user_obj': user})


class GroupListView(SuperAdminMixin, ListView):
    model = Group
    template_name = 'users/group_list.html'
    context_object_name = 'groups'
    paginate_by = 25


class GroupCreateView(SuperAdminMixin, CreateView):
    model = Group
    form_class = GroupForm
    template_name = 'users/group_form.html'
    success_url = reverse_lazy('users:group_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        response = super().form_valid(form)
        members = form.cleaned_data.get('members', [])
        for member in members:
            GroupMembership.objects.get_or_create(
                user=member, group=self.object, defaults={'role': 'member'}
            )
        messages.success(self.request, _('Grupo creado exitosamente'))
        return response


class GroupUpdateView(SuperAdminMixin, UpdateView):
    model = Group
    form_class = GroupForm
    template_name = 'users/group_form.html'
    success_url = reverse_lazy('users:group_list')

    def form_valid(self, form):
        response = super().form_valid(form)
        members = form.cleaned_data.get('members', [])
        current_members = set(self.object.members.values_list('id', flat=True))
        new_members = set(m.id for m in members)
        for member_id in new_members - current_members:
            GroupMembership.objects.get_or_create(
                user_id=member_id, group=self.object, defaults={'role': 'member'}
            )
        GroupMembership.objects.filter(group=self.object, user_id__in=current_members - new_members).delete()
        messages.success(self.request, _('Grupo actualizado exitosamente'))
        return response


class GroupDeleteView(SuperAdminMixin, DeleteView):
    model = Group
    template_name = 'users/group_confirm_delete.html'
    success_url = reverse_lazy('users:group_list')

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, _('Grupo eliminado exitosamente'))
        return super().delete(request, *args, **kwargs)


class GroupDetailView(SuperAdminMixin, DetailView):
    model = Group
    template_name = 'users/group_detail.html'
    context_object_name = 'group_obj'
