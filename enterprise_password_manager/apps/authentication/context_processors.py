from django.conf import settings


def theme(request):
    theme = request.COOKIES.get('theme', 'light')
    return {'current_theme': theme}


def sso_status(request):
    sso_enabled = False
    try:
        from apps.sso.models import SSOConfiguration
        sso_config = SSOConfiguration.objects.filter(is_active=True).first()
        sso_enabled = sso_config is not None
    except Exception:
        pass
    return {'sso_enabled': sso_enabled}
