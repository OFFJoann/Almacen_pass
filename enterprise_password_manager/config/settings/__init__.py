from decouple import config as decouple_config

environment = decouple_config('ENVIRONMENT', default='development')

if environment == 'production':
    from .production import *
else:
    from .development import *
