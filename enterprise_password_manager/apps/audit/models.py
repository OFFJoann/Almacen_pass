import uuid
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.conf import settings


class AuditLog(models.Model):
    ACTION_CHOICES = [
        ('LOGIN', _('Inicio de sesión')),
        ('LOGOUT', _('Cierre de sesión')),
        ('LOGIN_FAILED', _('Inicio de sesión fallido')),
        ('PASSWORD_CREATED', _('Contraseña creada')),
        ('PASSWORD_EDITED', _('Contraseña editada')),
        ('PASSWORD_DELETED', _('Contraseña eliminada')),
        ('PASSWORD_VIEWED', _('Contraseña consultada')),
        ('PASSWORD_IMPORTED', _('Contraseña importada')),
        ('PASSWORD_EXPORTED', _('Contraseña exportada')),
        ('PASSWORD_SHARED', _('Contraseña compartida')),
        ('SHARE_REVOKED', _('Compartición revocada')),
        ('USER_CREATED', _('Usuario creado')),
        ('USER_EDITED', _('Usuario editado')),
        ('USER_DELETED', _('Usuario eliminado')),
        ('USER_DISABLED', _('Usuario deshabilitado')),
        ('USER_ENABLED', _('Usuario habilitado')),
        ('GROUP_CREATED', _('Grupo creado')),
        ('GROUP_EDITED', _('Grupo editado')),
        ('GROUP_DELETED', _('Grupo eliminado')),
        ('MFA_ENABLED', _('MFA habilitado')),
        ('MFA_DISABLED', _('MFA deshabilitado')),
        ('SSO_CONFIGURED', _('SSO configurado')),
        ('SSO_ENABLED', _('SSO habilitado')),
        ('SSO_DISABLED', _('SSO deshabilitado')),
        ('POLICY_CHANGED', _('Política cambiada')),
        ('SETTINGS_CHANGED', _('Configuración cambiada')),
        ('FORCE_PASSWORD_CHANGE', _('Forzar cambio de contraseña')),
        ('SESSION_REVOKED', _('Sesión revocada')),
        ('EXPORT_VAULT', _('Exportar bóveda')),
        ('IMPORT_VAULT', _('Importar bóveda')),
        ('DATABASE_BACKUP', _('Backup de base de datos')),
        ('DATABASE_RESTORE', _('Restauración de base de datos')),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='audit_logs'
    )
    action = models.CharField(_('acción'), max_length=50, choices=ACTION_CHOICES)
    details = models.TextField(_('detalles'), blank=True, default='')
    result = models.CharField(_('resultado'), max_length=20, choices=[
        ('success', _('Éxito')),
        ('failure', _('Fallo')),
        ('pending', _('Pendiente')),
    ], default='success')
    ip_address = models.GenericIPAddressField(_('dirección IP'), blank=True, null=True)
    user_agent = models.TextField(_('agente de usuario'), blank=True, default='')
    browser = models.CharField(_('navegador'), max_length=100, blank=True, default='')
    os = models.CharField(_('sistema operativo'), max_length=100, blank=True, default='')
    device = models.CharField(_('dispositivo'), max_length=100, blank=True, default='')
    created_at = models.DateTimeField(_('creado el'), default=timezone.now)

    class Meta:
        verbose_name = _('registro de auditoría')
        verbose_name_plural = _('registros de auditoría')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['action']),
            models.Index(fields=['-created_at']),
            models.Index(fields=['ip_address']),
        ]

    def __str__(self):
        user_email = self.user.email if self.user else 'Anonymous'
        return f'{user_email} - {self.action} @ {self.created_at}'
