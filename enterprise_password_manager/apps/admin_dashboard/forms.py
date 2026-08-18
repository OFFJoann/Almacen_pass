from django import forms
from apps.users.models import User


class ApiTokenForm(forms.Form):
    name = forms.CharField(
        label='Nombre del token',
        max_length=150,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. Informes PowerBI'}),
        help_text='Identificador para reconocer para qué se usa este token.',
    )
    user = forms.ModelChoiceField(
        label='Usuario',
        queryset=User.objects.filter(is_active=True).order_by('email'),
        widget=forms.Select(attrs={'class': 'form-control select2'}),
        required=False,
        help_text='Deja en blanco para crearlo a tu nombre. Los administradores pueden crear tokens para otros usuarios.',
    )
    expires_at = forms.DateTimeField(
        label='Fecha de caducidad',
        required=False,
        widget=forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
        help_text='Opcional. Si se omite, el token no caduca.',
    )
