import os

bind = "0.0.0.0:8001"
workers = 4
threads = 2
timeout = 120
accesslog = "-"
errorlog = "-"


def post_fork(server, worker):
    """Pre-cargar las URLs (urlconf) al arrancar cada worker para evitar que
    el primer request pague el costo (1.2s+) de la resolución lazy de URLs."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    try:
        import django

        django.setup()
        from django.urls import get_resolver

        get_resolver().url_patterns
        from django.urls import reverse

        for name in ("authentication:login", "authentication:emergency_contact"):
            try:
                reverse(name)
            except Exception:
                pass
    except Exception as exc:  # noqa: BLE001 - no cortar el arranque del worker
        server.log.error("gunicorn preload urls failed: %r", exc)
