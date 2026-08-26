import json
from django import forms
from django.utils.translation import gettext_lazy as _
from .models import Secret, SecretShare


class SecretForm(forms.ModelForm):
    notes = forms.CharField(
        label=_('Notas'), required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3})
    )
    expires_at = forms.DateTimeField(
        label=_('Fecha de vencimiento'), required=False,
        widget=forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'})
    )

    class Meta:
        model = Secret
        fields = ['name', 'notes', 'expires_at']

    def __init__(self, *args, **kwargs):
        self.secret_type = kwargs.pop('secret_type', None)
        super().__init__(*args, **kwargs)
        self.fields['name'].widget.attrs.update({'class': 'form-control'})


class ApiKeyForm(SecretForm):
    provider = forms.CharField(
        label=_('Proveedor'), required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: AWS, Stripe, Google...'})
    )
    api_key = forms.CharField(
        label=_('API Key'), required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'autocomplete': 'off'})
    )
    endpoint_url = forms.URLField(
        label=_('URL Endpoint'), required=False,
        widget=forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://'})
    )

    def save(self, commit=True):
        secret = super().save(commit=False)
        secret.type = 'api_key'
        secret.set_data({
            'provider': self.cleaned_data.get('provider', ''),
            'api_key': self.cleaned_data.get('api_key', ''),
            'endpoint_url': self.cleaned_data.get('endpoint_url', ''),
        })
        secret.set_notes(self.cleaned_data.get('notes', ''))
        if commit:
            secret.save()
        return secret


class SshKeyForm(SecretForm):
    host = forms.CharField(
        label=_('Host'), required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: servidor.ejemplo.com'})
    )
    port = forms.IntegerField(
        label=_('Puerto'), required=False, initial=22,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 65535})
    )
    username = forms.CharField(
        label=_('Usuario'), required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    private_key = forms.CharField(
        label=_('Clave Privada'), required=True,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 6, 'placeholder': '-----BEGIN OPENSSH PRIVATE KEY-----\n...'})
    )
    public_key = forms.CharField(
        label=_('Clave Pública'), required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'ssh-rsa AAA...'})
    )
    passphrase = forms.CharField(
        label=_('Frase de Paso'), required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'autocomplete': 'off'})
    )

    def save(self, commit=True):
        secret = super().save(commit=False)
        secret.type = 'ssh_key'
        secret.set_data({
            'host': self.cleaned_data.get('host', ''),
            'port': str(self.cleaned_data.get('port', 22)),
            'username': self.cleaned_data.get('username', ''),
            'private_key': self.cleaned_data.get('private_key', ''),
            'public_key': self.cleaned_data.get('public_key', ''),
            'passphrase': self.cleaned_data.get('passphrase', ''),
        })
        secret.set_notes(self.cleaned_data.get('notes', ''))
        if commit:
            secret.save()
        return secret


class CreditCardForm(SecretForm):
    card_number = forms.CharField(
        label=_('Número de Tarjeta'), required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'autocomplete': 'off', 'placeholder': '1234 5678 9012 3456'})
    )
    card_holder = forms.CharField(
        label=_('Titular'), required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre en la tarjeta'})
    )
    expiry_month = forms.ChoiceField(
        label=_('Mes de Vencimiento'), required=True,
        choices=[(str(i).zfill(2), str(i).zfill(2)) for i in range(1, 13)],
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    expiry_year = forms.ChoiceField(
        label=_('Año de Vencimiento'), required=True,
        choices=[(str(i), str(i)) for i in range(2026, 2041)],
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    cvv = forms.CharField(
        label=_('CVV'), required=True, max_length=4,
        widget=forms.TextInput(attrs={'class': 'form-control', 'autocomplete': 'off', 'placeholder': '123'})
    )
    brand = forms.ChoiceField(
        label=_('Marca'), required=False,
        choices=[('', '---------'), ('visa', 'Visa'), ('mastercard', 'MasterCard'), ('amex', 'American Express'),
                 ('discover', 'Discover'), ('diners', 'Diners Club'), ('other', 'Otra')],
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    def save(self, commit=True):
        secret = super().save(commit=False)
        secret.type = 'credit_card'
        secret.set_data({
            'card_number': self.cleaned_data.get('card_number', ''),
            'card_holder': self.cleaned_data.get('card_holder', ''),
            'expiry_month': self.cleaned_data.get('expiry_month', ''),
            'expiry_year': self.cleaned_data.get('expiry_year', ''),
            'cvv': self.cleaned_data.get('cvv', ''),
            'brand': self.cleaned_data.get('brand', ''),
        })
        secret.set_notes(self.cleaned_data.get('notes', ''))
        if commit:
            secret.save()
        return secret


class CustomSecretForm(SecretForm):
    custom_fields = forms.CharField(
        label=_('Campos personalizados'),
        required=True,
        widget=forms.Textarea(attrs={
            'class': 'form-control', 'rows': 6,
            'placeholder': 'nombre=valor\nemail=user@ejemplo.com\nurl=https://...',
        }),
        help_text=_('Ingresa un campo por línea con el formato: nombre=valor')
    )

    def clean_custom_fields(self):
        raw = self.cleaned_data.get('custom_fields', '')
        fields = []
        for line in raw.strip().split('\n'):
            line = line.strip()
            if not line:
                continue
            if '=' not in line:
                raise forms.ValidationError(_('Cada línea debe tener formato: nombre=valor'))
            name, value = line.split('=', 1)
            fields.append({'name': name.strip(), 'value': value.strip()})
        if not fields:
            raise forms.ValidationError(_('Debes ingresar al menos un campo'))
        return fields

    def save(self, commit=True):
        secret = super().save(commit=False)
        secret.type = 'custom'
        secret.set_data({'fields': self.cleaned_data.get('custom_fields', [])})
        secret.set_notes(self.cleaned_data.get('notes', ''))
        if commit:
            secret.save()
        return secret


class SecretShareForm(forms.ModelForm):
    class Meta:
        model = SecretShare
        fields = ['shared_with_user', 'shared_with_group', 'permission', 'expires_at']
        widgets = {
            'shared_with_user': forms.Select(attrs={'class': 'form-control select2'}),
            'shared_with_group': forms.Select(attrs={'class': 'form-control select2'}),
            'permission': forms.Select(attrs={'class': 'form-control'}),
            'expires_at': forms.DateTimeInput(attrs={
                'class': 'form-control', 'type': 'datetime-local'
            }),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user:
            from apps.users.models import User
            self.fields['shared_with_user'].queryset = User.objects.filter(
                is_active=True
            ).exclude(pk=user.pk)
            self.fields['shared_with_user'].required = False
            self.fields['shared_with_group'].required = False

    def clean(self):
        cleaned_data = super().clean()
        user = cleaned_data.get('shared_with_user')
        group = cleaned_data.get('shared_with_group')
        if not user and not group:
            raise forms.ValidationError(_('Selecciona un usuario o grupo para compartir'))
        return cleaned_data
