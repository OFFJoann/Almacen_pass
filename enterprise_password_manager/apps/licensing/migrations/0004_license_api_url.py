from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('licensing', '0003_alter_license_license_key'),
    ]

    operations = [
        migrations.AddField(
            model_name='license',
            name='api_url',
            field=models.URLField(blank=True, default='', help_text='URL del servicio externo de licencias (ej. https://licencias.midominio.com)'),
        ),
    ]
