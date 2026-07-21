from django.apps import AppConfig

class SSOConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.sso'
    label = 'sso'
    verbose_name = 'SSO'
