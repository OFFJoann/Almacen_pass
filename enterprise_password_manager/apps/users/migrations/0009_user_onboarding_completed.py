from django.db import migrations, models
import django.utils.timezone


def mark_existing_users_completed(apps, schema_editor):
    User = apps.get_model('users', 'User')
    User.objects.filter(onboarding_completed=False).update(onboarding_completed=True)


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0008_ipgeocache'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='onboarding_completed',
            field=models.BooleanField(default=False, help_text='Indica si el usuario ya realizó el recorrido guiado de bienvenida.', verbose_name='guía de bienvenida completada'),
        ),
        migrations.RunPython(
            mark_existing_users_completed,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
