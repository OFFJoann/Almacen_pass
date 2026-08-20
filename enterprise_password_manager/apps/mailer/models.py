import uuid
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from apps.passwords.encryption import encrypt_field, decrypt_field


class SMTPSettings(models.Model):
    ENCRYPTION_CHOICES = [
        ('ssl', _('SSL (cifrado implícito)')),
        ('tls', _('STARTTLS (TLS)')),
        ('none', _('Sin cifrado')),
    ]

    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    company_name = models.CharField(_('nombre de la empresa'), max_length=255, blank=True, default='TICO BOX')
    host = models.CharField(_('servidor SMTP'), max_length=255, default='smtp.gmail.com')
    port = models.PositiveIntegerField(_('puerto'), default=587)
    username = models.CharField(_('usuario'), max_length=255, blank=True, default='')
    password_encrypted = models.TextField(_('contraseña cifrada'), blank=True, default='')
    password_nonce = models.TextField(blank=True, default='')
    password_salt = models.TextField(blank=True, default='')
    encryption = models.CharField(
        _('tipo de cifrado'), max_length=10,
        choices=ENCRYPTION_CHOICES, default='tls'
    )
    from_email = models.EmailField(_('correo remitente'), max_length=255, blank=True, default='')
    from_name = models.CharField(_('nombre del remitente'), max_length=255, blank=True, default='TICO BOX')
    timeout = models.PositiveIntegerField(_('tiempo de espera (s)'), default=30)
    is_active = models.BooleanField(_('activo'), default=False)
    updated_at = models.DateTimeField(_('actualizado el'), auto_now=True)

    class Meta:
        verbose_name = _('configuración SMTP')
        verbose_name_plural = _('configuración SMTP')

    def __str__(self):
        return self.host or 'Sin configurar'

    def save(self, *args, **kwargs):
        self.id = 1
        super().save(*args, **kwargs)

    @classmethod
    def get_singleton(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def set_password(self, plaintext):
        if not plaintext:
            return
        encrypted = encrypt_field(plaintext)
        self.password_encrypted = encrypted['ciphertext']
        self.password_nonce = encrypted['nonce']
        self.password_salt = encrypted['salt']

    def get_password(self):
        if not self.password_encrypted:
            return ''
        return decrypt_field(self.password_encrypted, self.password_nonce, self.password_salt)


class NotificationGroup(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(_('nombre'), max_length=150)
    description = models.TextField(_('descripción'), blank=True, default='')
    is_active = models.BooleanField(_('habilitado'), default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='created_notification_groups'
    )
    created_at = models.DateTimeField(_('creado el'), default=timezone.now)
    updated_at = models.DateTimeField(_('actualizado el'), auto_now=True)
    enterprise_groups = models.ManyToManyField(
        'users.Group', blank=True, related_name='notification_groups',
        verbose_name=_('grupos de la empresa'),
        help_text=_('Los miembros activos de estos grupos recibirán las notificaciones automáticamente.'),
    )

    class Meta:
        verbose_name = _('grupo de notificaciones')
        verbose_name_plural = _('grupos de notificaciones')
        ordering = ['name']

    def __str__(self):
        return self.name


class NotificationRecipient(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group = models.ForeignKey(
        NotificationGroup, on_delete=models.CASCADE, related_name='recipients'
    )
    email = models.EmailField(_('correo'), max_length=255)
    name = models.CharField(_('nombre'), max_length=255, blank=True, default='')
    is_active = models.BooleanField(_('activo'), default=True)
    created_at = models.DateTimeField(_('creado el'), default=timezone.now)

    class Meta:
        verbose_name = _('destinatario')
        verbose_name_plural = _('destinatarios')
        ordering = ['email']
        unique_together = [('group', 'email')]

    def __str__(self):
        return f'{self.email} ({self.group.name})'


class NotificationEvent(models.Model):
    CATEGORY_CHOICES = [
        ('password', _('Contraseñas')),
        ('secret', _('Secretos')),
        ('user', _('Usuarios')),
        ('security', _('Seguridad')),
        ('domain', _('Dominios')),
        ('analysis', _('Análisis')),
        ('system', _('Sistema')),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(_('código'), max_length=100, unique=True)
    name = models.CharField(_('nombre'), max_length=255)
    description = models.TextField(_('descripción'), blank=True, default='')
    category = models.CharField(_('categoría'), max_length=20, choices=CATEGORY_CHOICES, default='system')
    icon = models.CharField(_('icono'), max_length=50, blank=True, default='bell')
    available_variables = models.JSONField(_('variables disponibles'), default=list, blank=True)
    is_active = models.BooleanField(_('activo'), default=True)
    is_personal = models.BooleanField(
        _('notificación personal del usuario'), default=False,
        help_text=_('Si es True, la notificación se envía directamente al usuario involucrado '
                    'y no es configurable por grupos de notificaciones.'),
    )
    order = models.PositiveIntegerField(_('orden'), default=0)

    class Meta:
        verbose_name = _('evento de notificación')
        verbose_name_plural = _('eventos de notificación')
        ordering = ['order', 'name']

    def __str__(self):
        return self.name


class GroupNotificationEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group = models.ForeignKey(
        NotificationGroup, on_delete=models.CASCADE, related_name='event_configs'
    )
    event = models.ForeignKey(
        NotificationEvent, on_delete=models.CASCADE, related_name='group_configs'
    )
    is_enabled = models.BooleanField(_('habilitado'), default=True)
    updated_at = models.DateTimeField(_('actualizado el'), auto_now=True)

    class Meta:
        verbose_name = _('evento por grupo')
        verbose_name_plural = _('eventos por grupo')
        unique_together = [('group', 'event')]

    def __str__(self):
        return f'{self.group.name} -> {self.event.name}'


class EmailTemplate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.OneToOneField(
        NotificationEvent, on_delete=models.CASCADE, related_name='template'
    )
    subject = models.CharField(_('asunto'), max_length=255, blank=True, default='')
    body_html = models.TextField(_('contenido HTML'), blank=True, default='')
    body_text = models.TextField(_('contenido texto'), blank=True, default='')
    updated_at = models.DateTimeField(_('actualizado el'), auto_now=True)

    class Meta:
        verbose_name = _('plantilla de correo')
        verbose_name_plural = _('plantillas de correo')

    def __str__(self):
        return f'Plantilla: {self.event.name}'


class EmailLog(models.Model):
    STATUS_CHOICES = [
        ('sent', _('Enviado')),
        ('failed', _('Fallido')),
        ('test', _('Prueba')),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(
        NotificationEvent, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='email_logs'
    )
    group = models.ForeignKey(
        NotificationGroup, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='email_logs'
    )
    recipient = models.EmailField(_('destinatario'), max_length=255)
    subject = models.CharField(_('asunto'), max_length=255, blank=True, default='')
    status = models.CharField(_('estado'), max_length=10, choices=STATUS_CHOICES, default='sent')
    error = models.TextField(_('error'), blank=True, default='')
    created_at = models.DateTimeField(_('enviado el'), default=timezone.now)

    class Meta:
        verbose_name = _('registro de correo')
        verbose_name_plural = _('registros de correo')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f'{self.recipient} - {self.subject} ({self.status})'
