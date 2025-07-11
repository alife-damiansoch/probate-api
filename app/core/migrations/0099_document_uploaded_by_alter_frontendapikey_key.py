# Generated by Django 5.2.1 on 2025-07-02 09:50

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0098_document_is_manual_upload_alter_frontendapikey_key'),
    ]

    operations = [
        migrations.AddField(
            model_name='document',
            name='uploaded_by',
            field=models.ForeignKey(blank=True, default=None, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='documents_uploaded_by', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='frontendapikey',
            name='key',
            field=models.CharField(default='8iNawHFJT12ALHHDAoVolV2HTbZ2x7hnDd8yhgOtoGM', max_length=64, unique=True),
        ),
    ]
