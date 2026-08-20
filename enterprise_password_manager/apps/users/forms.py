from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.utils.translation import gettext_lazy as _
from .models import User, Group


class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ('email', 'full_name', 'phone')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-control'})


class CustomUserChangeForm(UserChangeForm):
    class Meta:
        model = User
        fields = ('email', 'full_name', 'phone', 'is_active', 'force_password_change')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-control'})


class UserCreateForm(forms.ModelForm):
    ADMIN_ROLES = ('superadmin', 'admin_usuarios')

    password = forms.CharField(
        label=_('Contraseña'),
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        required=False,
    )
    password_confirm = forms.CharField(
        label=_('Confirmar Contraseña'),
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        required=False,
    )

    class Meta:
        model = User
        fields = ('email', 'full_name', 'phone', 'is_active', 'role')
        widgets = {
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'full_name': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'role': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        self.request_user = kwargs.pop('request_user', None)
        super().__init__(*args, **kwargs)
        if not self.request_user or not self.request_user.is_superadmin():
            # Un admin (no superadmin) solo puede crear usuarios estándar (SSO, sin contraseña local).
            self.fields.pop('role', None)
            self.fields.pop('password', None)
            self.fields.pop('password_confirm', None)
        else:
            self.fields['password'].widget.attrs.update({'data-pw': '1'})
            self.fields['password_confirm'].widget.attrs.update({'data-pw': '1'})

    def clean(self):
        cleaned = super().clean()
        role = cleaned.get('role')
        password = cleaned.get('password')
        if role in self.ADMIN_ROLES:
            if not password:
                self.add_error('password', _('Los administradores deben tener una contraseña local.'))
            elif len(password) < 12:
                self.add_error('password', _('La contraseña debe tener al menos 12 caracteres.'))
        return cleaned

    def clean_password_confirm(self):
        password = self.cleaned_data.get('password')
        password_confirm = self.cleaned_data.get('password_confirm')
        if password and password_confirm and password != password_confirm:
            raise forms.ValidationError(_('Las contraseñas no coinciden'))
        return password_confirm

    def save(self, commit=True):
        user = super().save(commit=False)
        password = self.cleaned_data.get('password')
        if password:
            user.set_password(password)
        else:
            # Usuario solo SSO: sin contraseña local utilizable.
            user.set_unusable_password()
        if commit:
            user.save()
        return user


class UserEditForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ('email', 'full_name', 'phone', 'is_active', 'role', 'force_password_change',
                  'emergency_contact_name', 'emergency_contact_email')
        widgets = {
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'full_name': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'role': forms.Select(attrs={'class': 'form-control'}),
            'force_password_change': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'emergency_contact_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre del contacto'}),
            'emergency_contact_email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'contacto@example.com'}),
        }

    def __init__(self, *args, **kwargs):
        self.request_user = kwargs.pop('request_user', None)
        super().__init__(*args, **kwargs)
        if not self.request_user or not self.request_user.is_superadmin():
            self.fields.pop('role')

    def clean(self):
        cleaned = super().clean()
        return cleaned


class GroupForm(forms.ModelForm):
    members = forms.ModelMultipleChoiceField(
        queryset=User.objects.filter(is_active=True),
        widget=forms.SelectMultiple(attrs={'class': 'form-control select2'}),
        required=False
    )

    class Meta:
        model = Group
        fields = ('name', 'description', 'members', 'min_password_length', 'trash_retention_days', 'session_days', 'allow_export')
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'min_password_length': forms.NumberInput(attrs={'class': 'form-control', 'min': 4, 'max': 128}),
            'trash_retention_days': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 365}),
            'session_days': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 365}),
            'allow_export': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
