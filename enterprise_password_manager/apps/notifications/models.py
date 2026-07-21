import uuid
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.conf import settings


class Notification(models.Model):
    TYPE_CHOICES = [
        ('info', _('Información')),
        ('warning', _('Advertencia')),
        ('success', _('Éxito')),
        ('error', _('Error')),
        ('security', _('Alerta de seguridad')),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='notifications'
    )
    title = models.CharField(_('título'), max_length=255)
    message = models.TextField(_('mensaje'))
    notification_type = models.CharField(
        _('tipo'), max_length=20, choices=TYPE_CHOICES, default='info'
    )
    is_read = models.BooleanField(_('leído'), default=False)
    read_at = models.DateTimeField(_('leído el'), null=True, blank=True)
    action_url = models.CharField(_('URL de acción'), max_length=500, blank=True, default='')
    created_at = models.DateTimeField(_('creado el'), default=timezone.now)

    class Meta:
        verbose_name = _('notificación')
        verbose_name_plural = _('notificaciones')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['is_read']),
        ]

    def __str__(self):
        return f'{self.user.email} - {self.title}'

    def mark_as_read(self):
        self.is_read = True
        self.read_at = timezone.now()
        self.save(update_fields=['is_read', 'read_at'])
