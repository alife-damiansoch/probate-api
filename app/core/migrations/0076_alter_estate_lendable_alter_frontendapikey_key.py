# Generated by Django 5.2.1 on 2025-06-05 13:54

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0075_alter_estate_lendable_alter_frontendapikey_key'),
    ]

    operations = [
        migrations.AlterField(
            model_name='estate',
            name='lendable',
            field=models.BooleanField(default=None, null=True),
        ),
        migrations.AlterField(
            model_name='frontendapikey',
            name='key',
            field=models.CharField(default='EAa-dFyhBGdB5b8znKhkKHQQkBE3m3ATtJmWQiOeuzQ', max_length=64, unique=True),
        ),
    ]
