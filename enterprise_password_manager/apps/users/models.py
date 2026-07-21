import uuid
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from .managers import UserManager


class User(AbstractBaseUser, PermissionsMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(_('correo electrónico'), unique=True, max_length=255)
    full_name = models.CharField(_('nombre completo'), max_length=255)
    phone = models.CharField(_('teléfono'), max_length=50, blank=True, default='')
    avatar = models.ImageField(_('avatar'), upload_to='avatars/', blank=True, null=True)
    is_active = models.BooleanField(_('activo'), default=True)
    is_staff = models.BooleanField(_('es staff'), default=False)
    is_superuser = models.BooleanField(_('es superusuario'), default=False)
    force_password_change = models.BooleanField(_('forzar cambio de contraseña'), default=False)
    security_score = models.FloatField(_('puntaje de seguridad'), default=0.0)
    last_login_ip = models.GenericIPAddressField(_('última IP de acceso'), blank=True, null=True)
    last_login_user_agent = models.TextField(_('último user agent'), blank=True, default='')
    last_activity = models.DateTimeField(_('última actividad'), null=True, blank=True)
    mfa_enabled = models.BooleanField(_('MFA activado'), default=False)
    mfa_secret = models.CharField(_('secreto MFA'), max_length=64, blank=True, default='')
    trusted_devices = models.JSONField(_('dispositivos confiables'), default=list, blank=True)
    preferences = models.JSONField(_('preferencias'), default=dict, blank=True)
    created_at = models.DateTimeField(_('creado el'), default=timezone.now)
    updated_at = models.DateTimeField(_('actualizado el'), auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['full_name']

    class Meta:
        verbose_name = _('usuario')
        verbose_name_plural = _('usuarios')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['is_active']),
            models.Index(fields=['security_score']),
        ]

    def __str__(self):
        return self.email

    def get_full_name(self):
        return self.full_name

    def get_short_name(self):
        return self.email.split('@')[0]


class Group(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(_('nombre'), max_length=150, unique=True)
    description = models.TextField(_('descripción'), blank=True, default='')
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name='created_groups'
    )
    members = models.ManyToManyField(
        User, through='GroupMembership', related_name='custom_groups'
    )
    created_at = models.DateTimeField(_('creado el'), default=timezone.now)
    updated_at = models.DateTimeField(_('actualizado el'), auto_now=True)

    class Meta:
        verbose_name = _('grupo')
        verbose_name_plural = _('grupos')
        ordering = ['name']

    def __str__(self):
        return self.name


class GroupMembership(models.Model):
    ROLE_CHOICES = [
        ('member', _('Miembro')),
        ('admin', _('Admin')),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='group_memberships')
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='memberships')
    role = models.CharField(_('rol'), max_length=20, choices=ROLE_CHOICES, default='member')
    joined_at = models.DateTimeField(_('unido el'), default=timezone.now)

    class Meta:
        verbose_name = _('membresía de grupo')
        verbose_name_plural = _('membresías de grupo')
        unique_together = [('user', 'group')]

    def __str__(self):
        return f'{self.user.email} -> {self.group.name} ({self.role})'


class LoginHistory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='login_history')
    ip_address = models.GenericIPAddressField(_('dirección IP'))
    user_agent = models.TextField(_('agente de usuario'), blank=True, default='')
    browser = models.CharField(_('navegador'), max_length=100, blank=True, default='')
    os = models.CharField(_('sistema operativo'), max_length=100, blank=True, default='')
    device = models.CharField(_('dispositivo'), max_length=100, blank=True, default='')
    success = models.BooleanField(_('éxito'), default=True)
    failure_reason = models.CharField(_('motivo de fallo'), max_length=255, blank=True, default='')
    session_key = models.CharField(_('clave de sesión'), max_length=255, blank=True, default='')
    login_at = models.DateTimeField(_('acceso el'), default=timezone.now)
    logout_at = models.DateTimeField(_('cierre el'), null=True, blank=True)

    class Meta:
        verbose_name = _('historial de acceso')
        verbose_name_plural = _('historiales de acceso')
        ordering = ['-login_at']
        indexes = [
            models.Index(fields=['user', '-login_at']),
            models.Index(fields=['ip_address']),
        ]

    def __str__(self):
        return f'{self.user.email} @ {self.login_at}'


class ActiveSession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='active_sessions')
    session_key = models.CharField(_('clave de sesión'), max_length=255, unique=True)
    ip_address = models.GenericIPAddressField(_('dirección IP'))
    user_agent = models.TextField(_('agente de usuario'), blank=True, default='')
    browser = models.CharField(_('navegador'), max_length=100, blank=True, default='')
    os = models.CharField(_('sistema operativo'), max_length=100, blank=True, default='')
    device = models.CharField(_('dispositivo'), max_length=100, blank=True, default='')
    is_mfa_verified = models.BooleanField(_('MFA verificado'), default=False)
    is_trusted = models.BooleanField(_('dispositivo confiable'), default=False)
    last_activity = models.DateTimeField(_('última actividad'), default=timezone.now)
    started_at = models.DateTimeField(_('iniciado el'), default=timezone.now)
    expires_at = models.DateTimeField(_('expira el'))

    class Meta:
        verbose_name = _('sesión activa')
        verbose_name_plural = _('sesiones activas')
        ordering = ['-last_activity']
        indexes = [
            models.Index(fields=['user', '-last_activity']),
            models.Index(fields=['session_key']),
        ]

    def __str__(self):
        return f'{self.user.email} - {self.ip_address}'
