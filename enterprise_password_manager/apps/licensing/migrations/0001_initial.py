import uuid

import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='Installation',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('installation_id', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
            ],
            options={'verbose_name': 'Instalación', 'verbose_name_plural': 'Instalación'},
        ),
        migrations.CreateModel(
            name='License',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('license_key', models.TextField(blank=True, help_text='Clave de licencia firmada')),
                ('max_users', models.PositiveIntegerField(blank=True, null=True)),
                ('expires_at', models.DateTimeField(blank=True, null=True)),
                ('installation_id', models.CharField(blank=True, default='', max_length=64)),
                ('issued_at', models.DateTimeField(blank=True, null=True)),
                ('activated_at', models.DateTimeField(blank=True, null=True)),
                ('last_checked_at', models.DateTimeField(blank=True, null=True)),
                ('is_valid', models.BooleanField(default=False)),
                ('error', models.CharField(blank=True, default='', max_length=255)),
            ],
            options={'verbose_name': 'Licencia', 'verbose_name_plural': 'Licencia'},
        ),
    ]
