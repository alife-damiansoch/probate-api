# Generated by Django 5.2.1 on 2025-06-18 03:03

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0084_alter_frontendapikey_key_applicationprocessingstatus'),
    ]

    operations = [
        migrations.AlterField(
            model_name='frontendapikey',
            name='key',
            field=models.CharField(default='1OA5A1pTqwM7a7M39uV2VZILiva5KCIEZ8o6k9OIlQw', max_length=64, unique=True),
        ),
        migrations.AlterField(
            model_name='securitiesquoted',
            name='lendable',
            field=models.BooleanField(default=False),
        ),
    ]
