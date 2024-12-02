import os
from django.core.management.base import BaseCommand
from cryptography.fernet import Fernet
from core.models import Applicant


class Command(BaseCommand):
    help = "Encrypt existing plain-text PPS numbers in the database."

    def handle(self, *args, **kwargs):
        # Retrieve the encryption key from the environment
        encryption_key = os.getenv("PPS_ENCRYPTION_KEY")
        if not encryption_key:
            self.stderr.write(self.style.ERROR("PPS_ENCRYPTION_KEY is not set."))
            return

        cipher = Fernet(encryption_key.encode())  # Initialize the cipher

        # Use defer to avoid triggering decryption logic in __getattribute__
        applicants = Applicant.objects.defer("pps_number").all()
        updated_count = 0

        for applicant in applicants:
            try:
                # Access the raw PPS value without triggering decryption
                raw_pps = Applicant.objects.filter(id=applicant.id).values_list(
                    "pps_number", flat=True
                ).first()

                # Skip if PPS is None
                if not raw_pps:
                    self.stdout.write(
                        self.style.WARNING(
                            f"Skipping Applicant ID {applicant.id}: PPS is None"
                        )
                    )
                    continue

                # Check if PPS is already encrypted
                if isinstance(raw_pps, memoryview):
                    raw_pps = raw_pps.tobytes()  # Convert memoryview to bytes

                if isinstance(raw_pps, bytes):
                    if raw_pps.startswith(b"gAAAA"):  # Fernet tokens typically start with 'gAAAA'
                        self.stdout.write(
                            self.style.WARNING(
                                f"Skipping Applicant ID {applicant.id}: PPS already encrypted"
                            )
                        )
                        continue
                elif isinstance(raw_pps, str):
                    # Convert string to bytes for encryption
                    raw_pps = raw_pps.encode()

                # Encrypt the raw PPS string
                self.stdout.write(f"PPS (before encryption): {raw_pps}")
                encrypted_pps = cipher.encrypt(raw_pps)
                # Update the PPS field directly
                Applicant.objects.filter(id=applicant.id).update(pps_number=encrypted_pps)
                updated_count += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Encrypted PPS for Applicant ID {applicant.id}"
                    )
                )
            except Exception as e:
                self.stderr.write(
                    self.style.ERROR(
                        f"Error processing Applicant ID {applicant.id}: {e}"
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully encrypted PPS numbers for {updated_count} applicants."
            )
        )
