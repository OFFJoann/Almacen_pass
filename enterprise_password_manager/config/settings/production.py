from .base import *

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

_DB_SECRET = get_secret(config('AWS_DB_SECRET_ID', default='pd/ticobox/config'))

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
