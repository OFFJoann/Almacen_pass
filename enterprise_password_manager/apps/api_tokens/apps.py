from django.apps import AppConfig


class ApiTokensConfig(AppConfig):
    default_auto_field = 'django.db.models.UUIDField'
    name = 'apps.api_tokens'
    verbose_name = 'Tokens de API'
