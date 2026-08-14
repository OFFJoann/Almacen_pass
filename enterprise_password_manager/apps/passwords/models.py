import uuid
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from .encryption import encrypt_field, decrypt_field


class Folder(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(_('nombre'), max_length=255)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='folders'
    )
    parent = models.ForeignKey(
        'self', on_delete=models.CASCADE, null=True, blank=True,
        related_name='children'
    )
    icon = models.CharField(_('icono'), max_length=50, blank=True, default='folder')
    color = models.CharField(_('color'), max_length=7, blank=True, default='')
    created_at = models.DateTimeField(_('creado el'), default=timezone.now)
    updated_at = models.DateTimeField(_('actualizado el'), auto_now=True)

    class Meta:
        verbose_name = _('carpeta')
        verbose_name_plural = _('carpetas')
        ordering = ['name']
        unique_together = [('name', 'user', 'parent')]

    def __str__(self):
        return self.name


class Category(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(_('nombre'), max_length=255)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='categories'
    )
    icon = models.CharField(_('icono'), max_length=50, blank=True, default='tag')
    color = models.CharField(_('color'), max_length=7, blank=True, default='')
    created_at = models.DateTimeField(_('creado el'), default=timezone.now)

    class Meta:
        verbose_name = _('categoría')
        verbose_name_plural = _('categorías')
        ordering = ['name']
        unique_together = [('name', 'user')]

    def __str__(self):
        return self.name


class Tag(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(_('nombre'), max_length=50)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='tags'
    )
    color = models.CharField(_('color'), max_length=7, blank=True, default='#6c757d')
    created_at = models.DateTimeField(_('creado el'), default=timezone.now)

    class Meta:
        verbose_name = _('etiqueta')
        verbose_name_plural = _('etiquetas')
        ordering = ['name']
        unique_together = [('name', 'user')]

    def __str__(self):
        return self.name


class Vault(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(_('nombre'), max_length=255, default='Mi Bóveda')
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='vault'
    )
    description = models.TextField(_('descripción'), blank=True, default='')
    created_at = models.DateTimeField(_('creado el'), default=timezone.now)
    updated_at = models.DateTimeField(_('actualizado el'), auto_now=True)

    class Meta:
        verbose_name = _('bóveda')
        verbose_name_plural = _('bóvedas')

    def __str__(self):
        return f"{self.user.email}'s Vault"

    @property
    def password_count(self):
        return self.entries.count()

    @property
    def shared_count(self):
        return Share.objects.filter(entry__vault=self).count()


class PasswordEntry(models.Model):
    SENSITIVITY_CHOICES = [
        ('low', _('Baja')),
        ('medium', _('Media')),
        ('high', _('Alta')),
        ('critical', _('Crítica')),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vault = models.ForeignKey(
        Vault, on_delete=models.CASCADE, related_name='entries'
    )
    name = models.CharField(_('nombre'), max_length=255)
    url = models.URLField(_('URL'), max_length=2048, blank=True, default='')
    username_encrypted = models.TextField(_('usuario cifrado'), blank=True, default='')
    username_nonce = models.TextField(blank=True, default='')
    username_salt = models.TextField(blank=True, default='')
    password_encrypted = models.TextField(_('contraseña cifrada'), blank=True, default='')
    password_nonce = models.TextField(blank=True, default='')
    password_salt = models.TextField(blank=True, default='')
    notes_encrypted = models.TextField(_('notas cifradas'), blank=True, default='')
    notes_nonce = models.TextField(blank=True, default='')
    notes_salt = models.TextField(blank=True, default='')
    totp_secret_encrypted = models.TextField(_('secreto TOTP cifrado'), blank=True, default='')
    totp_secret_nonce = models.TextField(blank=True, default='')
    totp_secret_salt = models.TextField(blank=True, default='')
    folder = models.ForeignKey(
        Folder, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='entries'
    )
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='entries'
    )
    tags = models.ManyToManyField(Tag, blank=True, related_name='entries')
    sensitivity = models.CharField(
        _('sensibilidad'), max_length=20,
        choices=SENSITIVITY_CHOICES, default='medium'
    )
    is_favorite = models.BooleanField(_('favorito'), default=False)
    is_deleted = models.BooleanField(_('eliminado'), default=False)
    deleted_at = models.DateTimeField(_('eliminado el'), null=True, blank=True)
    is_obsolete = models.BooleanField(
        _('obsoleta'), default=False,
        help_text=_('Contraseña de origen desconocido que se conserva por seguridad en el módulo de obsoletos.')
    )
    obsoleted_at = models.DateTimeField(_('marcada obsoleta el'), null=True, blank=True)
    expires_at = models.DateTimeField(_('expira el'), null=True, blank=True)
    expiry_notified_at = models.DateTimeField(
        _('notificado de vencimiento el'), null=True, blank=True,
        help_text=_('Momento en que se envió la notificación de vencimiento.')
    )
    last_accessed = models.DateTimeField(_('último acceso'), null=True, blank=True)
    access_count = models.PositiveIntegerField(_('conteo de accesos'), default=0)
    version = models.PositiveIntegerField(_('versión'), default=1)
    is_compromised = models.BooleanField(_('comprometida'), default=False)
    compromised_checked_at = models.DateTimeField(_('última verificación'), null=True, blank=True)
    compromised_count = models.IntegerField(_('veces expuesta'), default=0)
    created_at = models.DateTimeField(_('creado el'), default=timezone.now)
    updated_at = models.DateTimeField(_('actualizado el'), auto_now=True)

    class Meta:
        verbose_name = _('entrada de contraseña')
        verbose_name_plural = _('entradas de contraseña')
        ordering = ['-is_favorite', 'name']
        indexes = [
            models.Index(fields=['vault', 'is_deleted']),
            models.Index(fields=['is_favorite']),
            models.Index(fields=['expires_at']),
            models.Index(fields=['is_compromised']),
        ]

    def __str__(self):
        return self.name

    def set_username(self, plaintext):
        encrypted = encrypt_field(plaintext)
        self.username_encrypted = encrypted['ciphertext']
        self.username_nonce = encrypted['nonce']
        self.username_salt = encrypted['salt']

    def get_username(self):
        if not self.username_encrypted:
            return ''
        return decrypt_field(self.username_encrypted, self.username_nonce, self.username_salt)

    def set_password(self, plaintext):
        encrypted = encrypt_field(plaintext)
        self.password_encrypted = encrypted['ciphertext']
        self.password_nonce = encrypted['nonce']
        self.password_salt = encrypted['salt']

    def get_password(self):
        if not self.password_encrypted:
            return ''
        return decrypt_field(self.password_encrypted, self.password_nonce, self.password_salt)

    def set_notes(self, plaintext):
        if not plaintext:
            self.notes_encrypted = ''
            self.notes_nonce = ''
            self.notes_salt = ''
            return
        encrypted = encrypt_field(plaintext)
        self.notes_encrypted = encrypted['ciphertext']
        self.notes_nonce = encrypted['nonce']
        self.notes_salt = encrypted['salt']

    def get_notes(self):
        if not self.notes_encrypted:
            return ''
        return decrypt_field(self.notes_encrypted, self.notes_nonce, self.notes_salt)

    def set_totp_secret(self, plaintext):
        if not plaintext:
            self.totp_secret_encrypted = ''
            self.totp_secret_nonce = ''
            self.totp_secret_salt = ''
            return
        encrypted = encrypt_field(plaintext)
        self.totp_secret_encrypted = encrypted['ciphertext']
        self.totp_secret_nonce = encrypted['nonce']
        self.totp_secret_salt = encrypted['salt']

    def get_totp_secret(self):
        if not self.totp_secret_encrypted:
            return ''
        return decrypt_field(self.totp_secret_encrypted, self.totp_secret_nonce, self.totp_secret_salt)

    @property
    def has_totp(self):
        if not self.totp_secret_encrypted:
            return False
        try:
            import pyotp
            pyotp.TOTP(self.get_totp_secret()).now()
            return True
        except Exception:
            return False

    def get_totp_uri(self):
        secret = self.get_totp_secret()
        if not secret:
            return ''
        import pyotp
        return pyotp.totp.TOTP(secret).provisioning_uri(
            name=self.get_username() or self.name,
            issuer_name='TICOlvidé'
        )

    def get_current_totp(self):
        secret = self.get_totp_secret()
        if not secret:
            return ''
        try:
            import pyotp
            return pyotp.TOTP(secret).now()
        except Exception:
            return ''


class PasswordHistory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    entry = models.ForeignKey(
        PasswordEntry, on_delete=models.CASCADE,
        related_name='password_history'
    )
    password_encrypted = models.TextField()
    password_nonce = models.TextField()
    password_salt = models.TextField()
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name='password_changes'
    )
    changes_summary = models.CharField(_('cambios'), max_length=255, blank=True, default='')
    created_at = models.DateTimeField(_('creado el'), default=timezone.now)

    class Meta:
        verbose_name = _('historial de contraseña')
        verbose_name_plural = _('historiales de contraseña')
        ordering = ['-created_at']

    def get_password(self):
        from .encryption import decrypt_field
        return decrypt_field(self.password_encrypted, self.password_nonce, self.password_salt)

    def __str__(self):
        return f'{self.entry.name} - {self.created_at}'


class Share(models.Model):
    PERMISSION_CHOICES = [
        ('read', _('Solo Lectura')),
        ('write', _('Puede Editar')),
        ('reshare', _('Puede Re-compartir')),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    entry = models.ForeignKey(
        PasswordEntry, on_delete=models.CASCADE,
        related_name='shares'
    )
    shared_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='shares_initiated'
    )
    shared_with_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        null=True, blank=True, related_name='shares_received'
    )
    shared_with_group = models.ForeignKey(
        'users.Group', on_delete=models.CASCADE,
        null=True, blank=True, related_name='shares_received'
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
        verbose_name = _('compartición')
        verbose_name_plural = _('comparticiones')
        indexes = [
            models.Index(fields=['entry', 'shared_with_user']),
            models.Index(fields=['shared_with_group']),
        ]

    def __str__(self):
        target = self.shared_with_user.email if self.shared_with_user else self.shared_with_group.name
        return f'{self.entry.name} -> {target}'

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


class ShareAccessLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    share = models.ForeignKey(
        Share, on_delete=models.CASCADE, related_name='access_logs'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE
    )
    action = models.CharField(_('acción'), max_length=50)
    ip_address = models.GenericIPAddressField(_('dirección IP'), blank=True, null=True)
    accessed_at = models.DateTimeField(_('accedido el'), default=timezone.now)

    class Meta:
        verbose_name = _('registro de acceso a compartición')
        verbose_name_plural = _('registros de acceso a comparticiones')
        ordering = ['-accessed_at']

    def __str__(self):
        return f'{self.user.email} - {self.action} - {self.accessed_at}'


class ShareRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', _('Pendiente')),
        ('approved', _('Aprobada')),
        ('denied', _('Denegada')),
        ('cancelled', _('Cancelada')),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    entry = models.ForeignKey(
        PasswordEntry, on_delete=models.CASCADE,
        related_name='share_requests'
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='share_requests_sent'
    )
    target_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='share_requests_addressed'
    )
    requested_days = models.PositiveIntegerField(
        _('días solicitados'), null=True, blank=True, default=None,
        help_text=_('Nulo significa compartición ilimitada.')
    )
    status = models.CharField(
        _('estado'), max_length=20, choices=STATUS_CHOICES, default='pending'
    )
    responded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='share_requests_answered'
    )
    created_at = models.DateTimeField(_('creado el'), default=timezone.now)
    responded_at = models.DateTimeField(_('respondido el'), null=True, blank=True)

    class Meta:
        verbose_name = _('solicitud de re-compartición')
        verbose_name_plural = _('solicitudes de re-compartición')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['entry']),
            models.Index(fields=['requested_by', 'status']),
        ]

    def __str__(self):
        return f'{self.requested_by.email} -> {self.target_user.email} ({self.entry.name})'


class Attachment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    entry = models.ForeignKey(
        PasswordEntry, on_delete=models.CASCADE,
        related_name='attachments'
    )
    file = models.FileField(_('archivo'), upload_to='attachments/')
    filename = models.CharField(_('nombre de archivo'), max_length=255)
    file_size = models.PositiveIntegerField(_('tamaño de archivo'))
    mime_type = models.CharField(_('tipo MIME'), max_length=100, blank=True, default='')
    uploaded_at = models.DateTimeField(_('subido el'), default=timezone.now)

    class Meta:
        verbose_name = _('archivo adjunto')
        verbose_name_plural = _('archivos adjuntos')

    def __str__(self):
        return self.filename
