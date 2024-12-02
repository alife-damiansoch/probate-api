from django.db import migrations
from cryptography.fernet import Fernet
from django.conf import settings
from django.db import models


def encrypt_existing_pps(apps, schema_editor):
    Applicant = apps.get_model("core", "Applicant")
    cipher = Fernet(settings.PPS_ENCRYPTION_KEY.encode())

    for applicant in Applicant.objects.all():
        if isinstance(applicant.pps_number, str):  # Encrypt plain text PPS numbers
            applicant.pps_number = cipher.encrypt(applicant.pps_number.encode())
            applicant.save()


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0060_alter_user_is_active"),
    ]

    operations = [
        migrations.AlterField(
            model_name="applicant",
            name="pps_number",
            field=models.BinaryField(null=True, blank=True),
        ),
        migrations.RunPython(encrypt_existing_pps),
    ]
