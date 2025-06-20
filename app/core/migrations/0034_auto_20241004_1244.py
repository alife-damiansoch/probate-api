# Generated by Django 3.2.25 on 2024-10-04 11:44

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0033_signeddocumentlog_signature_image_base64'),
    ]

    operations = [
        migrations.AddField(
            model_name='signeddocumentlog',
            name='device_browser_name',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='signeddocumentlog',
            name='device_browser_version',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='signeddocumentlog',
            name='device_platform',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='signeddocumentlog',
            name='device_screen_resolution',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AddField(
            model_name='signeddocumentlog',
            name='device_user_agent',
            field=models.TextField(blank=True, null=True),
        ),
    ]
