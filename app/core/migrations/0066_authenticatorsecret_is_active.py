# Generated by Django 3.2.25 on 2024-12-05 15:41

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0065_authenticatorsecret'),
    ]

    operations = [
        migrations.AddField(
            model_name='authenticatorsecret',
            name='is_active',
            field=models.BooleanField(default=False),
        ),
    ]
