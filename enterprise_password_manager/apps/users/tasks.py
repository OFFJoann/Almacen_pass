from celery import shared_task
from django.urls import reverse


def do_transfer(source_user_id, target_user_id, admin_email):
    from django.contrib.auth import get_user_model
    User = get_user_model()
    from apps.passwords.models import PasswordEntry, Folder, Vault
    from apps.notifications.models import Notification

    try:
        source = User.objects.get(pk=source_user_id)
        target = User.objects.get(pk=target_user_id)
    except User.DoesNotExist:
        return

    try:
        source_vault = source.vault
    except Vault.DoesNotExist:
        source_vault = None

    try:
        target_vault = target.vault
    except Vault.DoesNotExist:
        target_vault = Vault.objects.create(user=target, name='Mi Bóveda')

    if not source_vault:
        return

    folder_name = str(source)
    transfer_folder, _ = Folder.objects.get_or_create(
        name=folder_name,
        user=target,
        defaults={'parent': None},
    )

    entries = source_vault.entries.all()
    entries_count = entries.count()
    entries.update(vault=target_vault, folder=transfer_folder)

    Notification.objects.create(
        user=target,
        title='Bóveda recibida',
        message=(
            f'El administrador {admin_email} transfirió {entries_count} '
            f'contraseña{"s" if entries_count != 1 else ""} '
            f'del usuario {source.email} a tu bóveda, dentro de la carpeta "{folder_name}".'
        ),
        notification_type='info',
        action_url=reverse('passwords:vault'),
    )

    from apps.audit.models import AuditLog
    AuditLog.objects.create(
        user=None,
        action='USER_DELETED',
        details=(
            f'Bóveda de {source.email} transferida a {target.email} '
            f'por {admin_email}: {entries_count} entradas en carpeta "{folder_name}"'
        ),
        result='success',
    )


@shared_task
def transfer_vault(source_user_id, target_user_id, admin_email):
    return do_transfer(source_user_id, target_user_id, admin_email)
