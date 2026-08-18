from django.utils import timezone


def get_installation_id():
    from .models import Installation
    return Installation.get_id()


def active_user_count():
    from apps.users.models import User
    return User.objects.filter(is_active=True).count()


def get_license():
    from .models import License
    return License.get_instance()


def license_status_dict():
    return get_license().status()


def can_create_users(n=1):
    lic = get_license()
    if lic is None or not lic.license_key:
        return True
    status = lic.status()
    if not status['valid']:
        return False
    max_users = status['max_users']
    if max_users is None:
        return True
    return (status['used'] + n) <= max_users


def enforce_user_creation(n=1, active=True):
    from .exceptions import LicenseError

    lic = get_license()
    if lic is None or not lic.license_key:
        return

    st = lic.status()
    if not st['valid']:
        raise LicenseError(
            'No se pueden crear usuarios: la licencia no es válida o caducó (%s).'
            % (st['error'] or '')
        )
    if active:
        max_users = st['max_users']
        if max_users is not None and (st['used'] + n) > max_users:
            raise LicenseError(
                'Se alcanzó el límite de usuarios de la licencia (%s).' % max_users
            )


def license_block_reason():
    lic = get_license()
    st = lic.status()
    if not st['valid']:
        return 'No se pueden crear usuarios: la licencia no es válida o caducó (%s).' % (st['error'] or '')
    return 'No se pueden crear más usuarios: límite de la licencia alcanzado (%s).' % st['max_users']
