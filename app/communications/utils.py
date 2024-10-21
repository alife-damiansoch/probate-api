# communications/utils.py
import asyncio
import os
import uuid
import imaplib
import email
import re
from email.utils import parseaddr

import aiofiles
from aioimaplib import aioimaplib
from asgiref.sync import async_to_sync, sync_to_async
from channels.layers import get_channel_layer
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.mail import EmailMessage
from email.header import decode_header
from django.conf import settings
from core.models import EmailLog, Application, Solicitor, User, AssociatedEmail, Notification, Assignment, UserEmailLog
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


def send_email_f(sender, recipient, subject, message, attachments=None, application=None, solicitor_firm=None,
                 email_model=EmailLog):
    """
    Function to send an email using the SMTP settings.
    """
    if attachments is None:
        attachments = []
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
                email_log_entry = email_model.objects.create(
                    sender=sender,
                    recipient=recipient,
                    subject=subject,
                    message=message,
                    attachments=[att.file.name for att in attachments],  # Adjust attachment logic as necessary
                    application=application,
                    solicitor_firm=solicitor_firm
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

async def fetch_emails_for_imap_user(imap_user, log_model):
    imap_server = settings.IMAP_SERVER
    imap_port = settings.IMAP_PORT
    imap_password = settings.IMAP_PASSWORD
    mail = None  # Initialize mail to None to avoid reference before assignment

    print(f"Connecting to IMAP server: {imap_server}:{imap_port} as user {imap_user}...")

    try:
        mail = aioimaplib.IMAP4_SSL(imap_server, imap_port)
        await mail.wait_hello_from_server()
        await mail.login(imap_user, imap_password)
        print(f"Successfully logged in as {imap_user}.")

        await mail.select("inbox")

        status, messages = await mail.search('UNSEEN')
        unseen_emails = messages[0].split()
        print(f"Found {len(unseen_emails)} new unseen emails for {imap_user}.")

        for num in unseen_emails:
            try:
                status, data = await mail.fetch(num, "(RFC822)")
                msg = email.message_from_bytes(data[0][1])

                # Decode subject
                subject = decode_header(msg["Subject"])[0][0]
                if isinstance(subject, bytes):
                    subject = subject.decode()

                sender = parseaddr(msg.get("From"))[1]
                recipient = imap_user
                message = ""
                html_content = ""
                attachments = []
                original_filenames = []
                solicitor_firm = find_user_by_email(sender)
                message_id = msg.get("Message-ID", "")

                if msg.is_multipart():
                    for part in msg.walk():
                        content_type = part.get_content_type()
                        filename = part.get_filename()

                        if content_type == "text/html":
                            html_content += part.get_payload(decode=True).decode()
                        elif content_type == "text/plain" and not html_content:
                            message += part.get_payload(decode=True).decode()

                        if filename:
                            unique_filename = f"{uuid.uuid4()}{os.path.splitext(filename)[1]}"
                            file_path = os.path.join('email_attachments', unique_filename)

                            # Save file using async I/O
                            file_content = part.get_payload(decode=True)
                            async with aiofiles.open(file_path, 'wb') as f:
                                await f.write(file_content)

                            attachments.append(file_path)
                            original_filenames.append(filename)

                else:
                    message = msg.get_payload(decode=True).decode()

                # Save email log
                await sync_to_async(log_model.objects.create)(
                    sender=sender,
                    recipient=recipient,
                    subject=subject,
                    message=html_content if html_content else message,
                    is_sent=False,
                    message_id=message_id,
                    solicitor_firm=solicitor_firm,
                    attachments=attachments,
                    original_filenames=original_filenames,
                    seen=False
                )
                print(f"Email from {imap_user} logged successfully.")

            except Exception as e:
                print(f"Error processing email {num}: {e}")

    except Exception as e:
        print(f"Error in fetching emails for {imap_user}: {e}")

    finally:
        if mail:
            await mail.logout()  # Only call logout if mail was initialized successfully


async def fetch_emails():
    # Fetch emails for the default IMAP user
    await fetch_emails_for_imap_user(settings.IMAP_USER, EmailLog)

    # Fetch emails for users who are staff and belong to the "agents" team
    # Using sync_to_async to perform the Django ORM query in an async context
    users = await sync_to_async(lambda: list(User.objects.filter(is_staff=True, team__name="agents")))()

    # Create a list of tasks for each user
    tasks = [
        fetch_emails_for_imap_user(user.email, UserEmailLog) for user in users
    ]

    # Run all the tasks concurrently
    await asyncio.gather(*tasks)

# def _send_notification(email_log, message, recipient):
#     """Send a notification to the assigned user when an email log is created, updated, or deleted."""
#     try:
#         print("Creating notification object...")
#         notification = Notification.objects.create(
#             recipient=recipient,
#             text=message,
#             seen=False,
#             created_by=email_log.solicitor_firm,
#             application=None,
#         )
#         print(f"Notification created: {notification.id}")
#     except Exception as e:
#         print(f"Error creating notification: {e}")
#         return
#
#     try:
#         print("Getting channel layer...")
#         channel_layer = get_channel_layer()
#         print("Channel layer obtained.")
#     except Exception as e:
#         print(f"Error getting channel layer: {e}")
#         return
#
#     try:
#         print("Sending notification via channel layer...")
#         async_to_sync(channel_layer.group_send)(
#             'broadcast',
#             {
#                 'type': 'notification',
#                 'message': notification.text,
#                 'recipient': notification.recipient.email if notification.recipient else None,
#                 'notification_id': notification.id,
#                 'application_id': None,
#                 'seen': notification.seen,
#             }
#         )
#         print("Notification sent successfully.")
#     except Exception as e:
#         print(f"Error sending notification: {e}")
