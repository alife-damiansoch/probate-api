# communications/utils.py
import os
import uuid
import imaplib
import email
from django.core.mail import EmailMessage
from email.header import decode_header
from django.conf import settings
from core.models import EmailLog
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


# Function to send an email with or without attachments
# communications/utils.py


def send_email_f(sender, recipient, subject, message, application, attachments=None):
    """
    Function to send an email using the SMTP settings.
    """
    if attachments is None:
        attachments = []
    print(f"Sending email from {sender} to {recipient} with subject '{subject}'...")

    try:
        # Use EmailMessage and manually set Content-Type header for HTML
        email_message = EmailMessage(
            subject=subject,
            body=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[recipient],
        )

        # Set Content-Type to 'text/html' if HTML content is provided

        email_message.content_subtype = 'html'
        email_message.extra_headers = {'Content-Type': 'text/html'}

        print(email_message.__dict__)

        # Attach any files if provided
        for file_path in attachments:
            try:
                email_message.attach_file(file_path)
            except Exception as e:
                print(f"Failed to attach file {file_path}: {e}")

        email_backend = EmailBackend()
        connection = email_backend.open()

        if connection:
            print("Successfully connected!")
            try:
                email_backend.send_messages([email_message])
                print("Email sent successfully!")
            except Exception as e:
                print("Error sending mail: ", e)
            finally:
                email_backend.close()
                print("Connection closed.")
        else:
            print("Couldn't open the email backend connection.")

        # Log the email in the database
        EmailLog.objects.create(
            sender=sender,
            recipient=recipient,
            subject=subject,
            message=message,
            is_sent=True,
            attachments=attachments,
            application=application,
        )
        print(f"Email sent successfully to {recipient}")
    except Exception as e:
        print("Error opening connection: ", e)


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

    # Select the inbox
    mail.select("inbox")
    print("Selected the inbox folder.")

    # Search for all unseen emails
    status, messages = mail.search(None, 'UNSEEN')
    if status != "OK":
        print("Error during email search. No new emails found or issue with server connection.")
        return

    print(f"Found {len(messages[0].split())} new unseen emails.")

    # Process each unseen email
    for num in messages[0].split():
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

        sender = msg.get("From")
        recipient = imap_user
        message = ""
        html_content = ""  # To capture HTML content if present

        # Check for and extract attachments and message body
        if msg.is_multipart():
            print("Email is multipart, extracting message body and attachments...")
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition"))

                # If the part is text/html, prioritize it over text/plain
                if content_type == "text/html":
                    html_content += part.get_payload(decode=True).decode()
                elif content_type == "text/plain" and not html_content:
                    message += part.get_payload(decode=True).decode()

        else:
            message = msg.get_payload(decode=True).decode()

        # Save the received email to the database, preferring HTML content if available
        EmailLog.objects.create(
            sender=sender,
            recipient=recipient,
            subject=subject,
            message=html_content if html_content else message,  # Save HTML content if present
            is_sent=False  # Mark as a received email
        )

    print("All new emails have been processed.")
    mail.logout()
    print("Logged out from the IMAP server.")
