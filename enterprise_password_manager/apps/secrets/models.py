import uuid
import json
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from apps.passwords.encryption import encrypt_field, decrypt_field


class Secret(models.Model):
    TYPE_CHOICES = [
        ('api_key', _('API Key')),
        ('ssh_key', _('Clave SSH')),
        ('credit_card', _('Tarjeta de Crédito')),
        ('custom', _('Personalizado')),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='secrets'
    )
    type = models.CharField(_('tipo'), max_length=20, choices=TYPE_CHOICES)
    name = models.CharField(_('nombre'), max_length=255)
    data_encrypted = models.TextField(_('datos encriptados'))
    data_nonce = models.TextField(_('nonce datos'))
    data_salt = models.TextField(_('salt datos'))
    notes_encrypted = models.TextField(_('notas encriptadas'), blank=True, default='')
    notes_nonce = models.TextField(_('nonce notas'), blank=True, default='')
    notes_salt = models.TextField(_('salt notas'), blank=True, default='')
    is_deleted = models.BooleanField(_('eliminado'), default=False)
    deleted_at = models.DateTimeField(_('eliminado el'), null=True, blank=True)
    is_obsolete = models.BooleanField(
        _('obsoleto'), default=False,
        help_text=_('Secreto de origen desconocido que se conserva por seguridad en el módulo de obsoletos.')
    )
    obsoleted_at = models.DateTimeField(_('marcado obsoleto el'), null=True, blank=True)
    created_at = models.DateTimeField(_('creado el'), default=timezone.now)
    updated_at = models.DateTimeField(_('actualizado el'), auto_now=True)
    expires_at = models.DateTimeField(_('fecha de vencimiento'), null=True, blank=True)
    expiry_notified_at = models.DateTimeField(_('notificado el'), null=True, blank=True)

    class Meta:
        verbose_name = _('secreto')
        verbose_name_plural = _('secretos')
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    def is_expired(self):
        if self.expires_at and timezone.now() > self.expires_at:
            return True
        return False

    def set_data(self, data_dict):
        raw = json.dumps(data_dict)
        encrypted = encrypt_field(raw)
        self.data_encrypted = encrypted['ciphertext']
        self.data_nonce = encrypted['nonce']
        self.data_salt = encrypted['salt']

    def get_data(self):
        if not self.data_encrypted:
            return {}
        raw = decrypt_field(self.data_encrypted, self.data_nonce, self.data_salt)
        return json.loads(raw)

    def set_notes(self, notes):
        if notes:
            encrypted = encrypt_field(notes)
            self.notes_encrypted = encrypted['ciphertext']
            self.notes_nonce = encrypted['nonce']
            self.notes_salt = encrypted['salt']
        else:
            self.notes_encrypted = ''
            self.notes_nonce = ''
            self.notes_salt = ''

    def get_notes(self):
        if not self.notes_encrypted:
            return ''
        return decrypt_field(self.notes_encrypted, self.notes_nonce, self.notes_salt)

    def get_fields_display(self):
        data = self.get_data()
        if self.type == 'api_key':
            return [
                ('Proveedor', data.get('provider', '')),
                ('API Key', data.get('api_key', '')),
                ('URL Endpoint', data.get('endpoint_url', '')),
            ]
        elif self.type == 'ssh_key':
            return [
                ('Host', data.get('host', '')),
                ('Puerto', data.get('port', '22')),
                ('Usuario', data.get('username', '')),
                ('Clave Privada', data.get('private_key', '')),
                ('Clave Pública', data.get('public_key', '')),
                ('Frase de Paso', data.get('passphrase', '')),
            ]
        elif self.type == 'credit_card':
            return [
                ('Número', data.get('card_number', '')),
                ('Titular', data.get('card_holder', '')),
                ('Vence', f"{data.get('expiry_month', '')}/{data.get('expiry_year', '')}"),
                ('CVV', data.get('cvv', '')),
                ('Marca', data.get('brand', '')),
            ]
        elif self.type == 'custom':
            fields = data.get('fields', [])
            return [(f.get('name', ''), f.get('value', '')) for f in fields]
        return []


class SecretShare(models.Model):
    PERMISSION_CHOICES = [
        ('read', _('Solo Lectura')),
        ('write', _('Puede Editar')),
        ('reshare', _('Puede Re-compartir')),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    secret = models.ForeignKey(
        Secret, on_delete=models.CASCADE,
        related_name='shares'
    )
    shared_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='secret_shares_initiated'
    )
    shared_with_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        null=True, blank=True, related_name='secret_shares_received'
    )
    shared_with_group = models.ForeignKey(
        'users.Group', on_delete=models.CASCADE,
        null=True, blank=True, related_name='secret_shares_received'
    )
    permission = models.CharField(
        _('permiso'), max_length=20,
        choices=PERMISSION_CHOICES, default='read'
    )
    expires_at = models.DateTimeField(_('expira el'), null=True, blank=True)
    is_revoked = models.BooleanField(_('revocado'), default=False)
    revoked_at = models.DateTimeField(_('revocado el'), null=True, blank=True)
    created_at = models.DateTimeField(_('creado el'), default=timezone.now)

    class Meta:
        verbose_name = _('compartición de secreto')
        verbose_name_plural = _('comparticiones de secretos')
        indexes = [
            models.Index(fields=['secret', 'shared_with_user']),
            models.Index(fields=['shared_with_group']),
        ]

    def __str__(self):
        target = self.shared_with_user.email if self.shared_with_user else self.shared_with_group.name
        return f'{self.secret.name} -> {target}'

    def is_expired(self):
        if self.expires_at and timezone.now() > self.expires_at:
            return True
        return False

    def revoke(self):
        self.is_revoked = True
        self.revoked_at = timezone.now()
        self.save()

    def update_permission(self, new_permission, expires_at=None):
        self.permission = new_permission
        if expires_at is not None:
            self.expires_at = expires_at
        self.save(update_fields=['permission', 'expires_at'])
