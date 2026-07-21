from django import forms
from django.utils.translation import gettext_lazy as _
from .models import PasswordEntry, Folder, Category, Tag, Share


class PasswordEntryForm(forms.ModelForm):
    username = forms.CharField(
        label=_('Usuario'), max_length=255, required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'autocomplete': 'off'})
    )
    password = forms.CharField(
        label=_('Contraseña'), required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control', 'autocomplete': 'off',
            'data-password-toggle': 'true'
        })
    )
    notes = forms.CharField(
        label=_('Notas'), required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 4})
    )

    class Meta:
        model = PasswordEntry
        fields = ['name', 'url', 'folder', 'category', 'tags', 'sensitivity',
                   'is_favorite', 'expires_at']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://'}),
            'folder': forms.Select(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'tags': forms.SelectMultiple(attrs={'class': 'form-control select2'}),
            'sensitivity': forms.Select(attrs={'class': 'form-control'}),
            'is_favorite': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'expires_at': forms.DateTimeInput(attrs={
                'class': 'form-control', 'type': 'datetime-local'
            }),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user:
            self.fields['folder'].queryset = Folder.objects.filter(user=user)
            self.fields['category'].queryset = Category.objects.filter(user=user)
            self.fields['tags'].queryset = Tag.objects.filter(user=user)


class FolderForm(forms.ModelForm):
    class Meta:
        model = Folder
        fields = ['name', 'parent', 'icon', 'color']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'parent': forms.Select(attrs={'class': 'form-control'}),
            'icon': forms.TextInput(attrs={'class': 'form-control'}),
            'color': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user:
            self.fields['parent'].queryset = Folder.objects.filter(user=user)
            self.fields['parent'].required = False


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'icon', 'color']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'icon': forms.TextInput(attrs={'class': 'form-control'}),
            'color': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
        }


class TagForm(forms.ModelForm):
    class Meta:
        model = Tag
        fields = ['name', 'color']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'color': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
        }


class ShareForm(forms.ModelForm):
    class Meta:
        model = Share
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


class ImportForm(forms.Form):
    SOURCE_CHOICES = [
        ('bitwarden', _('Bitwarden')),
        ('keepass', _('KeePass')),
        ('csv', _('CSV')),
    ]
    source = forms.ChoiceField(
        label=_('Origen'), choices=SOURCE_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    file = forms.FileField(
        label=_('Archivo'),
        widget=forms.FileInput(attrs={'class': 'form-control'})
    )


class ExportForm(forms.Form):
    format = forms.ChoiceField(
        label=_('Formato'),
        choices=[('csv', 'CSV'), ('json', 'JSON')],
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    include_folders = forms.BooleanField(
        label=_('Incluir carpetas'), required=False, initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    encrypt = forms.BooleanField(
        label=_('Cifrar exportación'), required=False, initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
