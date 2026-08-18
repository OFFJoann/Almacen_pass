import uuid

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


def generate_token_key():
    import secrets
    return secrets.token_urlsafe(40)


class ApiToken(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='api_tokens',
        verbose_name='usuario',
    )
    name = models.CharField(
        _('nombre'),
        max_length=150,
        help_text=_('Identificador del token, p.ej. "Informes PowerBI".'),
    )
    key = models.CharField(
        _('clave'),
        max_length=100,
        unique=True,
        default=generate_token_key,
        editable=False,
    )
    created_at = models.DateTimeField(_('creado el'), default=timezone.now)
    expires_at = models.DateTimeField(
        _('caduca el'),
        null=True,
        blank=True,
        help_text=_('Fecha de caducidad. Déjalo vacío para que no expire.'),
    )
    is_active = models.BooleanField(_('activo'), default=True)
    last_used_at = models.DateTimeField(_('último uso'), null=True, blank=True)

    class Meta:
        verbose_name = _('token de API')
        verbose_name_plural = _('tokens de API')
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name} ({self.user.email})'

    @property
    def is_expired(self):
        return self.expires_at is not None and self.expires_at <= timezone.now()

    @property
    def is_valid(self):
        return self.is_active and not self.is_expired

    def mark_used(self):
        self.last_used_at = timezone.now()
        self.save(update_fields=['last_used_at'])
