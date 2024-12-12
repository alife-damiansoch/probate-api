# communications/utils.py
import asyncio
import os
import uuid
import imaplib
import email
import re
from email.mime.image import MIMEImage
from email.utils import parseaddr, make_msgid

import aiofiles
from aioimaplib import aioimaplib
from asgiref.sync import async_to_sync, sync_to_async
from channels.layers import get_channel_layer
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.mail import EmailMessage
from email.header import decode_header
from django.conf import settings
from django.db import transaction

from core.models import EmailLog, Application, Solicitor, User, AssociatedEmail, Notification, Assignment, \
    UserEmailLog
from django.core.mail.backends.smtp import EmailBackend
from django.core.mail import EmailMultiAlternatives

# Use the configured attachments directory from settings
ATTACHMENTS_DIR = os.path.join(settings.MEDIA_ROOT, 'email_attachments')

# Ensure the attachments directory exists
os.makedirs(ATTACHMENTS_DIR, exist_ok=True)


def generate_unique_filename(original_filename):
    """
      Generates a unique filename by appending a UUID to the original file's extension.

      This function extracts the file extension from the original filename and creates a new,
      unique filename with the same extension, ensuring the filename is unique across uploads.

      Parameters:
      - original_filename (str): The name of the original file including its extension.

      Returns:
      - str: A unique filename with the same extension as the original.
      """
    extension = os.path.splitext(original_filename)[1]  # Get the file extension
    unique_filename = f"{uuid.uuid4()}{extension}"  # Create a unique file name with the same extension
    return unique_filename


def find_user_by_email(sender):
    """
        Finds and returns a user associated with a given email address from the AssociatedEmail model.

        This function searches for a user linked to an email address in the `AssociatedEmail` model.
        If a matching email is found, it returns the associated user; otherwise, it returns None.

        Parameters:
        - sender (str): The email address to search for in the AssociatedEmail model.

        Returns:
        - User or None: The user associated with the email if found, else None.
        """
    associated_email = AssociatedEmail.objects.filter(email=sender)
    if associated_email:
        return associated_email.first().user
    else:
        return None


# Function to send an email with or without attachments
# communications/utils.py


def send_email_f(sender, recipient, subject, message, attachments=None, application=None, solicitor_firm=None,
                 email_model=EmailLog, use_info_email=False, save_in_email_log=True):
    """
      Sends an email with optional attachments and logs the email in the specified email model.

      This function creates an email log entry in the database, then constructs and sends an email with the specified
      sender, recipient, subject, and message. It optionally includes attachments, an associated application, and solicitor firm.
      If `use_info_email` is True, the email will be sent from the default info email specified in settings.

      Parameters:
      - sender (str): The email address of the sender.
      - recipient (str): The email address of the recipient.
      - subject (str): The subject of the email.
      - message (str): The message body of the email, expected to be in HTML format.
      - attachments (list, optional): A list of file objects to be attached to the email. Default is None.
      - application (Application, optional): An associated application instance, if applicable. Default is None.
      - solicitor_firm (SolicitorFirm, optional): The associated solicitor firm, if applicable. Default is None.
      - email_model (Model, optional): The Django model used for logging the email (default is `EmailLog`).
      - use_info_email (bool, optional): If True, sends the email from the default info email. Otherwise, uses the sender's address.

      Returns:
      - dict: A dictionary indicating success or an error message if the email fails to send or log.

      Process:
      1. Creates a unique filename for each attachment, saves it to the media storage, and processes it for sending.
      2. Creates an email log entry in the database with details such as sender, recipient, subject, message, and attachments.
      3. Constructs an email with the given details and attachments.
      4. Sends the email via an email backend, managing connections and error handling.

      Notes:
      - The function uses transactions to ensure both email logging and sending are handled atomically.
      - Email is sent with HTML content type, and a unique Message-ID is assigned to each email log entry.
      """

    if attachments is None:
        attachments = []
    processed_attachments = []
    original_filenames = []
    attachment_paths = []

    if attachments:
        for attachment in attachments:
            original_filename = getattr(attachment, 'name', 'attachment')  # Safe handling of name
            original_filenames.append(original_filename)

            unique_filename = f"{uuid.uuid4()}{os.path.splitext(original_filename)[1]}"
            file_path = os.path.join('email_attachments', unique_filename)

            saved_path = default_storage.save(file_path, ContentFile(attachment.read()))
            full_file_path = os.path.join(settings.MEDIA_ROOT, saved_path)
            attachment_paths.append(full_file_path)

            with open(full_file_path, 'rb') as f:
                file_data = f.read()
                processed_attachments.append((original_filename, file_data, attachment.content_type))

    try:
        # Wrap both the email log saving and email sending in a single transaction
        with transaction.atomic():
            # Save the email log in the database first
            if save_in_email_log:
                email_log_entry = email_model.objects.create(
                    sender=sender,
                    recipient=recipient,
                    subject=subject,
                    message=message,
                    attachments=attachment_paths,
                    application=application,
                    solicitor_firm=solicitor_firm,
                    seen=True,
                    message_id=str(uuid.uuid4()),  # Generate a unique Message-ID for the log
                    original_filenames=original_filenames if attachments else [],
                    is_sent=True,
                    send_from=settings.DEFAULT_FROM_EMAIL if use_info_email else sender,
                )
                # print(f"Email successfully logged in the database.")
            else:
                email_log_entry = UserEmailLog.objects.create(
                    sender=sender,
                    recipient=recipient,
                    subject=subject,
                    message=message,
                    attachments=attachment_paths,
                    application=application,
                    solicitor_firm=solicitor_firm,
                    seen=True,
                    message_id=str(uuid.uuid4()),  # Generate a unique Message-ID for the log
                    original_filenames=original_filenames if attachments else [],
                    is_sent=True,
                    send_from=settings.DEFAULT_FROM_EMAIL if use_info_email else sender,
                )

            # getting the sending user name to add it the the email
            # Assuming `sender` contains the email address of the user sending the email
            # Assuming `sender` contains the email address of the user sending the email
            user_model = get_user_model()
            try:
                # Get the user based on the email address
                user_instance = user_model.objects.get(email=sender)

                # Extract the user's name if it exists, otherwise default to email
                if user_instance.name:
                    # Get the first part of the full name (before any space)
                    sender_name = user_instance.name.split()[0]
                    from_email = f"{sender_name} <{email_log_entry.send_from}>"
                else:
                    from_email = sender
            except user_model.DoesNotExist:
                # If user does not exist, fallback to just the sender email
                from_email = sender

            # Create the email message
            email_message = EmailMessage(
                subject=subject,
                body=message,
                from_email=from_email,
                to=[recipient],
            )

            # Attach files to the email with their original filenames
            for file_tuple in processed_attachments:
                email_message.attach(*file_tuple)

            email_message.content_subtype = 'html'
            email_message.extra_headers = {
                'Message-ID': email_log_entry.message_id,
                'Content-Type': 'text/html',
            }

            # Send the email
            email_backend = EmailBackend()
            connection = email_backend.open()

            if connection:
                email_backend.send_messages([email_message])
                # print(f"Email sent successfully to {recipient}")

            # Close the email connection
            email_backend.close()

    except Exception as e:
        print(f"Error occurred: {e}")
        return {"error": str(e)}

    return {"success": "Email sent and logged successfully"}


# Function to Fetch Emails Using IMAP
# communications/utils.py

async def fetch_emails_for_imap_user(imap_user, log_model):
    """
      Asynchronously fetches unseen emails for a specified IMAP user and logs them using the specified model.

      This function connects to an IMAP server, retrieves unseen emails for a given user, processes each email to extract
      metadata, content, and attachments, and then logs them in the database using the specified log model.

      Parameters:
      - imap_user (str): The IMAP user/email address for which to fetch unseen emails.
      - log_model (Model): The Django model used for logging the emails, where each email and its details are saved.

      Process:
      1. Connects to the IMAP server specified in settings using SSL and logs in with the provided user.
      2. Searches the inbox for unseen emails.
      3. For each unseen email:
         - Retrieves metadata (sender, subject, message ID) and decodes the subject if needed.
         - Extracts HTML and/or plain text content, handling multipart emails by processing each part.
         - Saves any attachments with unique filenames, storing them in the media root folder.
         - Uses the `find_user_by_email` function to associate the email with a solicitor firm if applicable.
      4. Logs each email in the `log_model`, including attachments and the solicitor firm association if present.
      5. Handles any errors in fetching, processing, or logging each email individually.

      Notes:
      - The function uses `aioimaplib` for asynchronous IMAP connections and `aiofiles` for handling attachments.
      - Transactional operations are performed asynchronously to prevent blocking the event loop.
      - If an error occurs during connection or processing, it logs the error and attempts to continue.

      Returns:
      None. This function logs emails to the database without returning a value.

      Exceptions:
      - Logs any exceptions encountered during fetching, decoding, or saving emails, helping with troubleshooting.
      """
    imap_server = settings.IMAP_SERVER
    imap_port = settings.IMAP_PORT
    imap_password = settings.IMAP_PASSWORD
    mail = None

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
                email_id = num.decode('utf-8')
                print(f"Fetching email with ID: {email_id}...")

                status, data = await mail.fetch(email_id, "(RFC822)")

                if status != "OK" or not data or len(data) < 2 or not isinstance(data[1], (bytes, bytearray)):
                    print(f"Failed to fetch email {email_id}. Skipping.")
                    continue

                print(f"Successfully fetched email with ID: {email_id}.")
                msg = email.message_from_bytes(data[1])

                # Decode subject
                subject_tuple = decode_header(msg.get("Subject", "No Subject"))[0]
                subject, encoding = subject_tuple if isinstance(subject_tuple[0], (bytes, str)) else (
                    'No Subject', None)
                if isinstance(subject, bytes):
                    subject = subject.decode(encoding if encoding else 'utf-8')

                print(f"Email Subject: {subject}")

                # Print all headers for debugging
                # for header, value in msg.items():
                #     print(f"{header}: {value}")

                # Extract sender and recipient information
                sender = parseaddr(msg.get("From"))[1]
                recipient = parseaddr(msg.get("Delivered-To"))[1] or parseaddr(msg.get("To"))[1]

                # Handle forwarded emails by looking for additional headers like "X-Forwarded-To"
                if msg.get("X-Forwarded-To"):
                    recipient = parseaddr(msg.get("X-Forwarded-To"))[1]

                # If the recipient is still None, use imap_user as the recipient
                if not recipient:
                    recipient = imap_user

                # Log details
                # print(f"Sender: {sender}")
                # print(f"Recipient: {recipient}")

                message = ""
                html_content = ""
                attachments = []
                original_filenames = []

                # Use sync_to_async for find_user_by_email function
                solicitor_firm = await sync_to_async(find_user_by_email)(sender)
                message_id = msg.get("Message-ID", "")

                if msg.is_multipart():
                    for part in msg.walk():
                        content_type = part.get_content_type()
                        filename = part.get_filename()

                        if content_type == "text/html":
                            html_content += part.get_payload(decode=True).decode('utf-8', errors='replace')
                        elif content_type == "text/plain" and not html_content:
                            message += part.get_payload(decode=True).decode('utf-8', errors='replace')

                        if filename:
                            unique_filename = f"{uuid.uuid4()}{os.path.splitext(filename)[1]}"
                            file_path = os.path.join(settings.MEDIA_ROOT, 'email_attachments', unique_filename)

                            file_content = part.get_payload(decode=True)
                            async with aiofiles.open(file_path, 'wb') as f:
                                await f.write(file_content)

                            attachments.append(file_path)
                            original_filenames.append(filename)
                            # print(f"Attachment saved at: {file_path}")

                else:
                    message = msg.get_payload(decode=True).decode('utf-8', errors='replace')

                # Save the email asynchronously using sync_to_async
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
                # print(f"Email from {imap_user} logged successfully.")

            except Exception as e:
                print(f"Error processing email with ID {email_id}: {e}")

    except Exception as e:
        print(f"Error in fetching emails for {imap_user}: {e}")

    finally:
        if mail:
            await mail.logout()
            print("Logged out from the IMAP server.")


async def fetch_emails():
    """
      Asynchronously fetches emails for the default IMAP user and for staff users in the "agents" team.

      This function:
      1. Calls `fetch_emails_for_imap_user` for the default IMAP user specified in settings, logging emails to `EmailLog`.
      2. Queries all staff users in the "agents" team using the Django ORM, executed asynchronously with `sync_to_async`.
      3. Creates a list of tasks to fetch emails for each user in the "agents" team, logging emails to `UserEmailLog`.
      4. Runs all tasks concurrently using `asyncio.gather` to optimize performance and minimize wait times.

      Parameters:
      None

      Returns:
      None. This function runs email fetching tasks and logs emails without returning a value.

      Notes:
      - This function assumes the presence of the `User`, `EmailLog`, and `UserEmailLog` models.
      - Any exceptions raised in individual fetch tasks will be managed in `fetch_emails_for_imap_user`.
      """
    # Fetch emails for the default IMAP user
    await fetch_emails_for_imap_user(settings.IMAP_USER, EmailLog)

    """This part is turned off, because im using forwarders to forward all user related emails into the info inbox"""
    # # Fetch emails for users who are staff and belong to the "agents" team
    # # Using sync_to_async to perform the Django ORM query in an async context
    # users = await sync_to_async(lambda: list(User.objects.filter(is_staff=True, teams__name="agents")))()
    #
    # # Create a list of tasks for each user
    # tasks = [
    #     fetch_emails_for_imap_user(user.email, UserEmailLog) for user in users
    # ]
    #
    # # Run all the tasks concurrently
    # await asyncio.gather(*tasks)

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
