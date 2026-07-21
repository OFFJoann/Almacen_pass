from django import forms
from django.utils.translation import gettext_lazy as _


class VaultTransferForm(forms.Form):
    target_user = forms.EmailField(
        label=_('Transferir bóveda al usuario'),
        help_text=_('Ingrese el email exacto del usuario destino'),
        widget=forms.EmailInput(attrs={
            'placeholder': 'email@ejemplo.com',
            'class': 'vTextField',
            'style': 'width: 25em; font-size: 14px;',
            'autocomplete': 'off',
            'required': True,
        }),
    )

    def clean_target_user(self):
        email = self.cleaned_data['target_user']
        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            user = User.objects.get(email=email, is_active=True)
        except User.DoesNotExist:
            raise forms.ValidationError(_('No existe un usuario activo con ese email.'))
        return user
