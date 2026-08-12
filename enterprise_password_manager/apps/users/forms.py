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
    password = forms.CharField(
        label=_('Contraseña'),
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        min_length=12
    )
    password_confirm = forms.CharField(
        label=_('Confirmar Contraseña'),
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )

    class Meta:
        model = User
        fields = ('email', 'full_name', 'phone', 'is_active', 'role',
                  'emergency_contact_name', 'emergency_contact_email')
        widgets = {
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'full_name': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'role': forms.Select(attrs={'class': 'form-control'}),
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
        role = cleaned.get('role')
        if role in ('superadmin', 'admin_usuarios'):
            if not cleaned.get('emergency_contact_name'):
                self.add_error('emergency_contact_name', _('Los administradores deben registrar el nombre del contacto de emergencia.'))
            if not cleaned.get('emergency_contact_email'):
                self.add_error('emergency_contact_email', _('Los administradores deben registrar el correo del contacto de emergencia.'))
        return cleaned

    def clean_password_confirm(self):
        password = self.cleaned_data.get('password')
        password_confirm = self.cleaned_data.get('password_confirm')
        if password and password_confirm and password != password_confirm:
            raise forms.ValidationError(_('Las contraseñas no coinciden'))
        return password_confirm

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password'])
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
        role = cleaned.get('role')
        if role in ('superadmin', 'admin_usuarios'):
            if not cleaned.get('emergency_contact_name'):
                self.add_error('emergency_contact_name', _('Los administradores deben registrar el nombre del contacto de emergencia.'))
            if not cleaned.get('emergency_contact_email'):
                self.add_error('emergency_contact_email', _('Los administradores deben registrar el correo del contacto de emergencia.'))
        return cleaned


class GroupForm(forms.ModelForm):
    members = forms.ModelMultipleChoiceField(
        queryset=User.objects.filter(is_active=True),
        widget=forms.SelectMultiple(attrs={'class': 'form-control select2'}),
        required=False
    )

    class Meta:
        model = Group
        fields = ('name', 'description', 'members', 'min_password_length', 'trash_retention_days')
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'min_password_length': forms.NumberInput(attrs={'class': 'form-control', 'min': 4, 'max': 128}),
            'trash_retention_days': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 365}),
        }
