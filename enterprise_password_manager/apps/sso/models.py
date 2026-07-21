import uuid
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class SSOConfiguration(models.Model):
    PROVIDER_CHOICES = [
        ('azure', 'Microsoft Entra ID (Azure AD)'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    provider = models.CharField(
        _('proveedor'), max_length=50, choices=PROVIDER_CHOICES,
        default='azure'
    )
    tenant_id = models.CharField(_('ID de tenant'), max_length=255)
    client_id = models.CharField(_('ID de cliente'), max_length=255)
    client_secret = models.CharField(_('secreto de cliente'), max_length=500)
    redirect_uri = models.URLField(_('URI de redirección'), max_length=500)
    logout_uri = models.URLField(_('URI de cierre de sesión'), max_length=500, blank=True, default='')
    scopes = models.CharField(
        _('alcances'), max_length=500,
        default='openid profile email User.Read'
    )
    is_active = models.BooleanField(_('activo'), default=False)
    sync_groups = models.BooleanField(_('sincronizar grupos'), default=False)
    just_in_time_provisioning = models.BooleanField(
        _('aprovisionamiento justo a tiempo'), default=True
    )
    allow_local_auth = models.BooleanField(
        _('permitir autenticación local'), default=True
    )
    created_at = models.DateTimeField(_('creado el'), default=timezone.now)
    updated_at = models.DateTimeField(_('actualizado el'), auto_now=True)

    class Meta:
        verbose_name = _('configuración SSO')
        verbose_name_plural = _('configuraciones SSO')

    def __str__(self):
        return f'{self.get_provider_display()} - {"Activo" if self.is_active else "Inactivo"}'

    def save(self, *args, **kwargs):
        if self.is_active:
            SSOConfiguration.objects.filter(is_active=True).exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)

    def get_authorization_url(self):
        from urllib.parse import urlencode
        base = f'https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/authorize'
        params = {
            'client_id': self.client_id,
            'response_type': 'code',
            'redirect_uri': self.redirect_uri,
            'response_mode': 'query',
            'scope': self.scopes,
            'state': str(uuid.uuid4()),
        }
        return f'{base}?{urlencode(params)}'

    def get_logout_url(self):
        if self.logout_uri:
            return self.logout_uri
        return f'https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/logout?post_logout_redirect_uri={self.redirect_uri}'


class SSOLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    config = models.ForeignKey(
        SSOConfiguration, on_delete=models.CASCADE, related_name='logs'
    )
    user_email = models.EmailField(_('correo electrónico del usuario'), blank=True, default='')
    action = models.CharField(_('acción'), max_length=50)
    details = models.TextField(_('detalles'), blank=True, default='')
    success = models.BooleanField(_('éxito'), default=True)
    ip_address = models.GenericIPAddressField(_('dirección IP'), blank=True, null=True)
    created_at = models.DateTimeField(_('creado el'), default=timezone.now)

    class Meta:
        verbose_name = _('registro SSO')
        verbose_name_plural = _('registros SSO')
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user_email} - {self.action} @ {self.created_at}'
