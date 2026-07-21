from django import forms
from django.utils.translation import gettext_lazy as _
from .models import SSOConfiguration


class SSOConfigurationForm(forms.ModelForm):
    client_secret = forms.CharField(
        label=_('Secreto del Cliente'),
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        required=False,
        help_text=_('Dejar vacío para mantener el secreto actual')
    )

    class Meta:
        model = SSOConfiguration
        fields = [
            'provider', 'tenant_id', 'client_id', 'client_secret',
            'redirect_uri', 'logout_uri', 'scopes',
            'is_active', 'sync_groups', 'just_in_time_provisioning',
            'allow_local_auth',
        ]
        widgets = {
            'provider': forms.Select(attrs={'class': 'form-control'}),
            'tenant_id': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '00000000-0000-0000-0000-000000000000'}),
            'client_id': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '00000000-0000-0000-0000-000000000000'}),
            'redirect_uri': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://yourdomain.com/sso/callback/'}),
            'logout_uri': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://yourdomain.com/sso/logout/'}),
            'scopes': forms.TextInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'sync_groups': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'just_in_time_provisioning': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'allow_local_auth': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.client_secret:
            self.fields['client_secret'].required = False

    def clean_client_secret(self):
        client_secret = self.cleaned_data.get('client_secret')
        if not client_secret and self.instance and self.instance.pk:
            return self.instance.client_secret
        return client_secret
