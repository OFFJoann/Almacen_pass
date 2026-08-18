import uuid

from django.db import models
from django.utils import timezone


class Installation(models.Model):
    """Singleton that identifies this deployed instance (used to bind licenses)."""

    id = models.AutoField(primary_key=True)
    installation_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = 'Instalación'
        verbose_name_plural = 'Instalación'

    @classmethod
    def get_id(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return str(obj.installation_id)

    def __str__(self):
        return str(self.installation_id)


class License(models.Model):
    """Singleton holding the activated license (empresa + clave) and its validated limits."""

    id = models.AutoField(primary_key=True)
    company = models.CharField(max_length=150, blank=True, default='', help_text='Empresa/tenant asociada')
    api_url = models.URLField(blank=True, default='', help_text='URL del servicio externo de licencias (ej. https://licencias.midominio.com)')
    license_key = models.TextField(blank=True, help_text='Clave de licencia proporcionada por el proveedor')
    max_users = models.PositiveIntegerField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    installation_id = models.CharField(max_length=64, blank=True, default='')
    issued_at = models.DateTimeField(null=True, blank=True)
    activated_at = models.DateTimeField(null=True, blank=True)
    last_checked_at = models.DateTimeField(null=True, blank=True)
    is_valid = models.BooleanField(default=False)
    error = models.CharField(max_length=255, blank=True, default='')

    class Meta:
        verbose_name = 'Licencia'
        verbose_name_plural = 'Licencia'

    @classmethod
    def get_instance(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def verify(self):
        """Call the external license API (empresa + licencia). Returns (valid, payload, error)."""
        from django.conf import settings
        import requests

        if not self.company or not self.license_key:
            return False, None, 'Falta la empresa o la licencia'
        base = (self.api_url or getattr(settings, 'LICENSE_API_URL', 'http://127.0.0.1:8002')).rstrip('/')
        url = base if base.endswith('/licencias') else base + '/licencias'
        try:
            resp = requests.post(
                url,
                json={'empresa': self.company, 'licencia': self.license_key},
                timeout=10,
            )
        except requests.RequestException:
            return False, None, 'No se pudo contactar al servicio de licencias'
        if resp.status_code != 200:
            return False, None, 'Respuesta inválida del servicio de licencias'
        data = resp.json()
        if not data.get('valid'):
            return False, None, data.get('error', 'Licencia inválida')
        return True, data, ''

    def status(self):
        from django.utils import timezone
        from .utils import active_user_count

        configured = bool(self.license_key)
        if not configured:
            return {
                'configured': False,
                'valid': False,
                'error': 'Sin licencia activada',
                'max_users': None,
                'used': active_user_count(),
                'remaining': None,
                'expires_at': None,
            }
        # Usa el resultado guardado en la activación/revalidación (no llama la API en cada página).
        valid = self.is_valid
        error = self.error
        if valid and self.expires_at and self.expires_at < timezone.now():
            valid = False
            error = 'Licencia caducada'
        used = active_user_count()
        max_users = self.max_users
        remaining = (max_users - used) if max_users is not None else None
        expires_at = self.expires_at.isoformat() if self.expires_at else None
        return {
            'configured': True,
            'valid': valid,
            'error': error,
            'max_users': max_users,
            'used': used,
            'remaining': remaining,
            'expires_at': expires_at,
        }

    def __str__(self):
        return f'Licencia ({self.company or "?"}, max_users={self.max_users}, válida={self.is_valid})'
