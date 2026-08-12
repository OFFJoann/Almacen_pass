from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class SecretsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.secrets'
    verbose_name = _('Secretos')
