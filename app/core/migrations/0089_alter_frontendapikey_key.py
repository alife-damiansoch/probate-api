# Generated by Django 5.2.1 on 2025-06-19 22:34

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0088_alter_frontendapikey_key'),
    ]

    operations = [
        migrations.AlterField(
            model_name='frontendapikey',
            name='key',
            field=models.CharField(default='yzGM76rlwOInFA6RUPqjVQyNIPM_MPTX3VmFRSFUyWY', max_length=64, unique=True),
        ),
    ]
