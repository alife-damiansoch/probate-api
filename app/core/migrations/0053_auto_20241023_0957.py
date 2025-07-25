# Generated by Django 3.2.25 on 2024-10-23 08:57

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0052_auto_20241023_0907'),
    ]

    operations = [
        migrations.AddField(
            model_name='loan',
            name='is_paid_out',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='loan',
            name='paid_out_date',
            field=models.DateField(blank=True, null=True),
        ),
    ]
