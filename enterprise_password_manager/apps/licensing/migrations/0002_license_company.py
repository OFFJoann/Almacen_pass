from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('licensing', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='license',
            name='company',
            field=models.CharField(blank=True, default='', max_length=150, help_text='Empresa/tenant asociada'),
        ),
    ]
