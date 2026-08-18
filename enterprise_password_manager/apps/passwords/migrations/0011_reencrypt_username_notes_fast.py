from django.db import migrations


def reencrypt_username_notes(apps, schema_editor):
    from apps.passwords.encryption import (
        decrypt_field,
        encrypt_field_fast,
    )
    PasswordEntry = apps.get_model('passwords', 'PasswordEntry')
    for entry in PasswordEntry.objects.exclude(
        username_encrypted='', username_salt=''
    ).only('username_encrypted', 'username_nonce', 'username_salt'):
        try:
            plain = decrypt_field(
                entry.username_encrypted, entry.username_nonce, entry.username_salt
            )
        except Exception:
            continue
        enc = encrypt_field_fast(plain)
        entry.username_encrypted = enc['ciphertext']
        entry.username_nonce = enc['nonce']
        entry.username_salt = enc['salt']
        entry.save(update_fields=['username_encrypted', 'username_nonce', 'username_salt'])

    for entry in PasswordEntry.objects.exclude(
        notes_encrypted='', notes_salt=''
    ).only('notes_encrypted', 'notes_nonce', 'notes_salt'):
        try:
            plain = decrypt_field(
                entry.notes_encrypted, entry.notes_nonce, entry.notes_salt
            )
        except Exception:
            continue
        enc = encrypt_field_fast(plain)
        entry.notes_encrypted = enc['ciphertext']
        entry.notes_nonce = enc['nonce']
        entry.notes_salt = enc['salt']
        entry.save(update_fields=['notes_encrypted', 'notes_nonce', 'notes_salt'])


def reverse_reencrypt(apps, schema_editor):
    # No es trivial revertir sin la clave vieja; se deja como no-op seguro.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('passwords', '0010_passwordentry_password_entropy_and_more'),
    ]

    operations = [
        migrations.RunPython(reencrypt_username_notes, reverse_reencrypt),
    ]
