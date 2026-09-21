from .base import *

import os
import botocore
from ..aws_secrets import get_secret

DEBUG = False
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True

CORS_ORIGIN_ALLOW_ALL = False
CORS_ALLOWED_ORIGINS = config('CORS_ALLOWED_ORIGINS', default='https://example.com').split(',')

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = config('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = True
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='noreply@example.com')

SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True


def _load_db_secret():
    """Lee el secreto de base de datos desde AWS Secrets Manager.

    Si no hay credenciales AWS disponibles (por ejemplo durante el build de la
    imagen, cuando collectstatic importa estos settings pero la máquina no
    tiene credenciales), se cae a variables de entorno con sus valores por
    defecto para no romper la construcción. En producción real las credenciales
    AWS existen y siempre se usa el secreto.
    """
    try:
        return get_secret(config('AWS_DB_SECRET_ID', default='pd/ticobox/config'))
    except (
        botocore.exceptions.NoCredentialsError,
        botocore.exceptions.PartialCredentialsError,
        botocore.exceptions.CredentialRetrievalError,
        botocore.exceptions.TokenRetrievalError,
    ):
        return {
            'dbname': config('DB_NAME', default='epm_db'),
            'username': config('DB_USER', default='epm_user'),
            'password': config('DB_PASSWORD', default='epm_password'),
            'host': config('DB_HOST', default='db'),
            'port': config('DB_PORT', default='5432'),
        }


_DB_SECRET = _load_db_secret()

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': _DB_SECRET['dbname'],
        'USER': _DB_SECRET['username'],
        'PASSWORD': _DB_SECRET['password'],
        'HOST': _DB_SECRET['host'],
        'PORT': str(_DB_SECRET['port']),
        'CONN_MAX_AGE': 600,
        'OPTIONS': {
            'connect_timeout': 10,
        },
    }
}
