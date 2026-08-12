from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.utils.translation import gettext_lazy as _


class LoginForm(AuthenticationForm):
    username = forms.EmailField(
        label=_('Correo Electrónico'),
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'user@company.com',
            'autocomplete': 'email',
            'autofocus': True
        })
    )
    password = forms.CharField(
        label=_('Contraseña'),
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': '••••••••',
            'autocomplete': 'current-password'
        })
    )
    remember_me = forms.BooleanField(
        label=_('Recordarme'),
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({'class': 'form-control'})


class MFAForm(forms.Form):
    code = forms.CharField(
        label=_('Código de Autenticación'),
        max_length=6,
        min_length=6,
        widget=forms.TextInput(attrs={
            'class': 'form-control text-center',
            'placeholder': '000000',
            'autocomplete': 'one-time-code',
            'inputmode': 'numeric',
            'pattern': '[0-9]*'
        })
    )


class MFASetupForm(forms.Form):
    code = forms.CharField(
        label=_('Verificar Código'),
        max_length=6,
        min_length=6,
        widget=forms.TextInput(attrs={
            'class': 'form-control text-center',
            'placeholder': '000000',
            'autocomplete': 'one-time-code',
            'inputmode': 'numeric',
        })
    )


class PasswordResetRequestForm(forms.Form):
    email = forms.EmailField(
        label=_('Correo Electrónico'),
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'user@company.com'
        })
    )


class SetPasswordForm(forms.Form):
    password = forms.CharField(
        label=_('Nueva Contraseña'),
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        min_length=12
    )
    password_confirm = forms.CharField(
        label=_('Confirmar Contraseña'),
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )

    def clean_password_confirm(self):
        password = self.cleaned_data.get('password')
        password_confirm = self.cleaned_data.get('password_confirm')
        if password and password_confirm and password != password_confirm:
            raise forms.ValidationError(_('Las contraseñas no coinciden'))
        return password_confirm


class SecurityQuestionForm(forms.Form):
    answer = forms.CharField(
        label=_('Respuesta de Seguridad'),
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )


class EmergencyContactForm(forms.Form):
    emergency_contact_name = forms.CharField(
        label=_('Nombre del contacto de emergencia'),
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Nombre de la persona de confianza',
        })
    )
    emergency_contact_email = forms.EmailField(
        label=_('Correo del contacto de emergencia'),
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'contacto@example.com',
        })
    )
