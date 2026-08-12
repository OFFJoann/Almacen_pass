from django import forms
from django.utils.translation import gettext_lazy as _
from .models import (
    SMTPSettings, NotificationGroup, NotificationRecipient, EmailTemplate,
)


class SMTPSettingsForm(forms.ModelForm):
    password = forms.CharField(
        label=_('Contraseña'), required=False,
        widget=forms.PasswordInput(render_value=False),
        help_text=_('Déjalo en blanco para conservar la contraseña actual.'),
    )

    class Meta:
        model = SMTPSettings
        fields = [
            'company_name', 'host', 'port', 'username', 'password',
            'encryption', 'from_email', 'from_name', 'timeout', 'is_active',
        ]
        widgets = {
            'host': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'smtp.gmail.com'}),
            'port': forms.NumberInput(attrs={'class': 'form-control'}),
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'encryption': forms.Select(attrs={'class': 'form-select'}),
            'from_email': forms.EmailInput(attrs={'class': 'form-control'}),
            'from_name': forms.TextInput(attrs={'class': 'form-control'}),
            'company_name': forms.TextInput(attrs={'class': 'form-control'}),
            'timeout': forms.NumberInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password'].widget.attrs['class'] = 'form-control'
        self.fields['is_active'].widget.attrs['class'] = 'form-check-input'

    def save(self, commit=True):
        obj = super().save(commit=False)
        password = self.cleaned_data.get('password')
        if password:
            obj.set_password(password)
        if commit:
            obj.save()
        return obj


class TestEmailForm(forms.Form):
    to_email = forms.EmailField(
        label=_('Correo de prueba'),
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'destinatario@ejemplo.com'}),
    )


class NotificationGroupForm(forms.ModelForm):
    class Meta:
        model = NotificationGroup
        fields = ['name', 'description', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['is_active'].widget.attrs['class'] = 'form-check-input'


class NotificationRecipientForm(forms.ModelForm):
    class Meta:
        model = NotificationRecipient
        fields = ['email', 'name', 'is_active']
        widgets = {
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'destinatario@ejemplo.com'}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('Nombre (opcional)')}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['is_active'].widget.attrs['class'] = 'form-check-input'


class EmailTemplateForm(forms.ModelForm):
    class Meta:
        model = EmailTemplate
        fields = ['subject', 'body_html', 'body_text']
        widgets = {
            'subject': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Asunto del correo'}),
            'body_html': forms.Textarea(attrs={'class': 'form-control code-editor', 'rows': 16}),
            'body_text': forms.Textarea(attrs={'class': 'form-control code-editor', 'rows': 8}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['body_html'].help_text = _(
            'Puedes usar HTML. Incluye variables como {{ nombre_empresa }}, {{ usuario }}, {{ fecha }}.'
        )
        self.fields['body_text'].help_text = _(
            'Versión en texto plano (para clientes sin HTML). Deja vacío para usar el HTML.'
        )
