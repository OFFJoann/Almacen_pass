from .base import *

DEBUG = True
ALLOWED_HOSTS = ['localhost', '127.0.0.1', '*']

SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_SSL_REDIRECT = False

SESSION_ENGINE = 'django.contrib.sessions.backends.db'

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

CORS_ORIGIN_ALLOW_ALL = True

INSTALLED_APPS += ['debug_toolbar']
MIDDLEWARE.insert(
    next(i for i, m in enumerate(MIDDLEWARE) if 'AuthenticationMiddleware' in m) + 1,
    'debug_toolbar.middleware.DebugToolbarMiddleware'
)
INTERNAL_IPS = ['127.0.0.1']
DEBUG_TOOLBAR_CONFIG = {
    'SHOW_TOOLBAR_CALLBACK': lambda request: request.user.is_authenticated and request.user.is_staff,
}

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'epm-dev-cache',
    },
    'session': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'epm-dev-session',
    },
}

CELERY_TASK_ALWAYS_EAGER = True

SECURE_HSTS_SECONDS = 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False

AXES_ENABLED = False
