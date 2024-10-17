# communications/utils.py
import os
import uuid
import imaplib
import email
import re
from email.utils import parseaddr

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.mail import EmailMessage
from email.header import decode_header
from django.conf import settings
from core.models import EmailLog, Application, Solicitor, User, AssociatedEmail
from django.core.mail.backends.smtp import EmailBackend
from django.core.mail import EmailMultiAlternatives

# Use the configured attachments directory from settings
ATTACHMENTS_DIR = os.path.join(settings.MEDIA_ROOT, 'email_attachments')

# Ensure the attachments directory exists
os.makedirs(ATTACHMENTS_DIR, exist_ok=True)


def generate_unique_filename(original_filename):
    """
    Generate a unique file name based on the original file name.
    """
    extension = os.path.splitext(original_filename)[1]  # Get the file extension
    unique_filename = f"{uuid.uuid4()}{extension}"  # Create a unique file name with the same extension
    return unique_filename


def find_user_by_email(sender):
    associated_email = AssociatedEmail.objects.filter(email=sender)
    if associated_email:
        return associated_email.first().user
    else:
        return None


# Function to send an email with or without attachments
# communications/utils.py


def send_email_f(sender, recipient, subject, message, attachments=None, application=None, solicitor_firm=None):
    """
    Function to send an email using the SMTP settings.
    """
    processed_attachments = []
    original_filenames = []
    attachment_paths = []

    if attachments:
        for attachment in attachments:
            original_filenames.append(attachment.name)  # Log original filename
            # Generate a unique filename with the same extension for logging purposes only
            unique_filename = f"{uuid.uuid4()}{os.path.splitext(attachment.name)[1]}"
            file_path = os.path.join('email_attachments', unique_filename)  # Path within the media directory

            # Save the file to the media/email_attachments directory
            saved_path = default_storage.save(file_path, ContentFile(attachment.read()))  # Save the file content

            # Add the full path to the log
            full_file_path = os.path.join(settings.MEDIA_ROOT, saved_path)
            attachment_paths.append(full_file_path)

            # Reopen the file for reading as binary for email attachment
            with open(full_file_path, 'rb') as f:
                file_data = f.read()  # Read file in binary format
                processed_attachments.append((attachment.name, file_data, attachment.content_type))

    try:
        # Create the email message
        email_message = EmailMessage(
            subject=subject,
            body=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[recipient],
        )

        # Attach files to the email with their original filenames
        for file_tuple in processed_attachments:
            email_message.attach(*file_tuple)  # Attach with original name and binary content

        # Set HTML content
        email_message.content_subtype = 'html'

        # Generate a unique Message-ID
        message_id = str(uuid.uuid4())
        email_message.extra_headers = {
            'Message-ID': message_id,
            'Content-Type': 'text/html',
        }

        # Send the email
        email_backend = EmailBackend()
        connection = email_backend.open()

        if connection:
            try:
                email_backend.send_messages([email_message])
                print(f"Email sent successfully to {recipient}")

                # Log the email and attachments
                EmailLog.objects.create(
                    sender=sender,
                    recipient=recipient,
                    subject=subject,
                    message=message,
                    is_sent=True,
                    attachments=attachment_paths,  # Store full file paths
                    original_filenames=original_filenames,  # Store original file names
                    message_id=message_id,
                    application=application,
                    solicitor_firm=solicitor_firm,
                )
                print(f"Email successfully logged in the database.")

            except Exception as e:
                print(f"Error sending email to {recipient}: {e}")
            finally:
                email_backend.close()

    except Exception as e:
        print(f"Error occurred: {e}")


# Function to Fetch Emails Using IMAP
# communications/utils.py

def fetch_emails():
    print("Starting the email fetching process...")

    # Use settings loaded from .env
    imap_server = settings.IMAP_SERVER
    imap_port = settings.IMAP_PORT
    imap_user = settings.IMAP_USER
    imap_password = settings.IMAP_PASSWORD

    print(f"Connecting to IMAP server: {imap_server}:{imap_port} as user {imap_user}...")
    try:
        mail = imaplib.IMAP4_SSL(imap_server, imap_port)
        mail.login(imap_user, imap_password)
        print(f"Successfully connected to IMAP server and logged in as {imap_user}.")
    except Exception as e:
        print(f"Failed to connect to IMAP server: {e}")
        return

    try:
        # Select the inbox
        mail.select("inbox")
        print("Selected the inbox folder.")

        # Search for all unseen emails
        status, messages = mail.search(None, 'UNSEEN')
        if status != "OK":
            print("Error during email search. No new emails found or issue with server connection.")
            return

        unseen_emails = messages[0].split()
        print(f"Found {len(unseen_emails)} new unseen emails.")

        # Process each unseen email
        for num in unseen_emails:
            try:
                print(f"Fetching email with ID: {num}...")
                status, data = mail.fetch(num, "(RFC822)")
                if status != "OK":
                    print(f"Failed to fetch email {num}. Skipping to the next email.")
                    continue

                print(f"Successfully fetched email with ID: {num}.")
                msg = email.message_from_bytes(data[0][1])

                # Decode subject
                subject = decode_header(msg["Subject"])[0][0]
                if isinstance(subject, bytes):
                    subject = subject.decode()
                print(f"Email subject: {subject}")

                sender = parseaddr(msg.get("From"))[1]
                recipient = imap_user
                message = ""
                html_content = ""  # To capture HTML content if present
                attachments = []  # List to hold attachment file paths
                original_filenames = []  # To store original filenames for logging

                # Get the solicitor's firm by email
                solicitor_firm = find_user_by_email(sender)

                # Check the headers for a custom Message_ID
                message_id = msg.get("Message-ID", "")
                print(f"Message-ID: {message_id}")

                # Check for and extract attachments and message body
                if msg.is_multipart():
                    print("Email is multipart, extracting message body and attachments...")
                    for part in msg.walk():
                        content_type = part.get_content_type()
                        content_disposition = str(part.get("Content-Disposition"))
                        filename = part.get_filename()

                        # Print content type and disposition for debugging
                        print(f"Part content type: {content_type}")
                        print(f"Part content disposition: {content_disposition}")

                        # If the part is text/html, prioritize it over text/plain
                        if content_type == "text/html":
                            print("Processing HTML content...")
                            html_content += part.get_payload(decode=True).decode()
                        elif content_type == "text/plain" and not html_content:
                            print("Processing plain text content...")
                            message += part.get_payload(decode=True).decode()

                        # Process both inline and regular attachments
                        if filename:
                            try:
                                print(f"Found attachment: {filename}")
                                original_filenames.append(filename)

                                # Save the attachment to the 'email_attachments' directory
                                unique_filename = f"{uuid.uuid4()}{os.path.splitext(filename)[1]}"
                                file_path = os.path.join('email_attachments', unique_filename)

                                # Save the file using Django's default storage system
                                file_content = part.get_payload(decode=True)
                                saved_path = default_storage.save(file_path, ContentFile(file_content))
                                full_file_path = os.path.join(settings.MEDIA_ROOT, saved_path)
                                attachments.append(full_file_path)
                                print(f"Attachment saved at: {full_file_path}")
                            except Exception as e:
                                print(f"Failed to process attachment: {e}")
                else:
                    message = msg.get_payload(decode=True).decode()

                # Save the received email and its attachments to the database
                EmailLog.objects.create(
                    sender=sender,
                    recipient=recipient,
                    subject=subject,
                    message=html_content if html_content else message,  # Save HTML content if present
                    is_sent=False,  # Mark as a received email
                    message_id=message_id,
                    solicitor_firm=solicitor_firm,
                    attachments=attachments,  # Store attachment file paths
                    original_filenames=original_filenames,  # Store original attachment filenames
                )
                print("Email and attachments logged successfully.")

            except Exception as e:
                print(f"Error processing email with ID {num}: {e}")
                continue

    except Exception as e:
        print(f"Error in fetching emails: {e}")
    finally:
        mail.logout()
        print("Logged out from the IMAP server.")
