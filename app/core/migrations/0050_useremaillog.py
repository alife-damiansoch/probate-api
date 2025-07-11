# Generated by Django 3.2.25 on 2024-10-21 09:59

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0049_emaillog_seen'),
    ]

    operations = [
        migrations.CreateModel(
            name='UserEmailLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('sender', models.EmailField(max_length=254)),
                ('recipient', models.EmailField(max_length=254)),
                ('subject', models.CharField(max_length=255)),
                ('message', models.TextField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('is_sent', models.BooleanField(default=False)),
                ('attachments', models.JSONField(blank=True, null=True)),
                ('original_filenames', models.JSONField(blank=True, null=True)),
                ('message_id', models.CharField(blank=True, max_length=255, null=True)),
                ('seen', models.BooleanField(default=False)),
                ('application', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='core.application')),
                ('solicitor_firm', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'abstract': False,
            },
        ),
    ]
