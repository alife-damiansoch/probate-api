# communications/utils.py
import asyncio
import os
import uuid
import imaplib
import email
import re
import logging
import sys
import traceback
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

# Configure comprehensive logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

# Use the configured attachments directory from settings
ATTACHMENTS_DIR = os.path.join(settings.MEDIA_ROOT, 'email_attachments')

# Ensure the attachments directory exists
os.makedirs(ATTACHMENTS_DIR, exist_ok=True)
logger.info(f"Attachments directory configured: {ATTACHMENTS_DIR}")


def generate_unique_filename(original_filename):
    """
    Generates a unique filename by appending a UUID to the original file's extension.
    """
    logger.debug(f">>> Generating unique filename for: {original_filename}")
    try:
        extension = os.path.splitext(original_filename)[1]
        unique_filename = f"{uuid.uuid4()}{extension}"
        logger.debug(f">>> Generated unique filename: {unique_filename}")
        return unique_filename
    except Exception as e:
        logger.error(f">>> Error generating unique filename: {e}")
        return f"{uuid.uuid4()}.tmp"


def find_user_by_email(sender):
    """
    Finds and returns a user associated with a given email address from the AssociatedEmail model.
    """
    logger.debug(f">>> Looking up user for email: {sender}")
    try:
        associated_email = AssociatedEmail.objects.filter(email=sender)
        if associated_email:
            user = associated_email.first().user
            logger.debug(f">>> Found associated user: {user.email if user else 'None'}")
            return user
        else:
            logger.debug(f">>> No associated user found for email: {sender}")
            return None
    except Exception as e:
        logger.error(f">>> Error finding user by email {sender}: {e}")
        return None


def send_email_f(sender, recipient, subject, message, attachments=None, application=None, solicitor_firm=None,
                 email_model=EmailLog, use_info_email=False, save_in_email_log=True):
    """
    Sends an email with optional attachments and logs the email in the specified email model.
    """
    logger.info(f">>> Starting send_email_f - From: {sender}, To: {recipient}, Subject: {subject[:50]}...")

    if attachments is None:
        attachments = []

    processed_attachments = []
    original_filenames = []
    attachment_paths = []

    logger.debug(f">>> Processing {len(attachments)} attachments")

    if attachments:
        for i, attachment in enumerate(attachments):
            try:
                logger.debug(f">>> Processing attachment {i + 1}/{len(attachments)}")
                original_filename = getattr(attachment, 'name', 'attachment')
                original_filenames.append(original_filename)
                logger.debug(f">>> Original filename: {original_filename}")

                unique_filename = f"{uuid.uuid4()}{os.path.splitext(original_filename)[1]}"
                file_path = os.path.join('email_attachments', unique_filename)
                logger.debug(f">>> Saving to path: {file_path}")

                saved_path = default_storage.save(file_path, ContentFile(attachment.read()))
                full_file_path = os.path.join(settings.MEDIA_ROOT, saved_path)
                attachment_paths.append(full_file_path)
                logger.debug(f">>> Saved attachment to: {full_file_path}")

                with open(full_file_path, 'rb') as f:
                    file_data = f.read()
                    processed_attachments.append((original_filename, file_data, attachment.content_type))
                    logger.debug(f">>> Processed attachment: {original_filename}, size: {len(file_data)} bytes")

            except Exception as e:
                logger.error(f">>> Error processing attachment {i + 1}: {e}")
                logger.error(f">>> Attachment error traceback: {traceback.format_exc()}")

    try:
        logger.debug(">>> Starting database transaction")
        with transaction.atomic():
            # Save the email log in the database first
            if save_in_email_log:
                logger.debug(">>> Creating EmailLog entry")
                email_log_entry = email_model.objects.create(
                    sender=sender,
                    recipient=recipient,
                    subject=subject,
                    message=message,
                    attachments=attachment_paths,
                    application=application,
                    solicitor_firm=solicitor_firm,
                    seen=True,
                    message_id=str(uuid.uuid4()),
                    original_filenames=original_filenames if attachments else [],
                    is_sent=True,
                    send_from=settings.DEFAULT_FROM_EMAIL if use_info_email else sender,
                )
                logger.info(f">>> Email successfully logged in EmailLog with ID: {email_log_entry.id}")
            else:
                logger.debug(">>> Creating UserEmailLog entry")
                email_log_entry = UserEmailLog.objects.create(
                    sender=sender,
                    recipient=recipient,
                    subject=subject,
                    message=message,
                    attachments=attachment_paths,
                    application=application,
                    solicitor_firm=solicitor_firm,
                    seen=True,
                    message_id=str(uuid.uuid4()),
                    original_filenames=original_filenames if attachments else [],
                    is_sent=True,
                    send_from=settings.DEFAULT_FROM_EMAIL if use_info_email else sender,
                )
                logger.info(f">>> Email successfully logged in UserEmailLog with ID: {email_log_entry.id}")

            # Getting the sending user name to add it to the email
            logger.debug(f">>> Looking up user for sender: {sender}")
            user_model = get_user_model()
            try:
                user_instance = user_model.objects.get(email=sender)
                logger.debug(f">>> Found user: {user_instance.name if hasattr(user_instance, 'name') else 'No name'}")

                if hasattr(user_instance, 'name') and user_instance.name:
                    sender_name = user_instance.name.split()[0]
                    from_email = f"{sender_name} <{email_log_entry.send_from}>"
                    logger.debug(f">>> Using sender name: {from_email}")
                else:
                    from_email = sender
                    logger.debug(f">>> Using sender email: {from_email}")
            except user_model.DoesNotExist:
                from_email = sender
                logger.debug(f">>> User not found, using sender email: {from_email}")

            # Create the email message
            logger.debug(">>> Creating EmailMessage object")
            email_message = EmailMessage(
                subject=subject,
                body=message,
                from_email=from_email,
                to=[recipient],
            )

            # Attach files to the email with their original filenames
            logger.debug(f">>> Attaching {len(processed_attachments)} files to email")
            for i, file_tuple in enumerate(processed_attachments):
                try:
                    email_message.attach(*file_tuple)
                    logger.debug(f">>> Attached file {i + 1}: {file_tuple[0]}")
                except Exception as e:
                    logger.error(f">>> Error attaching file {i + 1}: {e}")

            email_message.content_subtype = 'html'
            email_message.extra_headers = {
                'Message-ID': email_log_entry.message_id,
                'Content-Type': 'text/html',
            }
            logger.debug(f">>> Email message configured with Message-ID: {email_log_entry.message_id}")

            # Send the email
            logger.debug(">>> Creating email backend connection")
            email_backend = EmailBackend()
            connection = email_backend.open()

            if connection:
                logger.debug(">>> Email backend connection opened successfully")
                try:
                    result = email_backend.send_messages([email_message])
                    logger.info(f">>> Email sent successfully to {recipient}, result: {result}")
                except Exception as e:
                    logger.error(f">>> Error sending email: {e}")
                    logger.error(f">>> Send error traceback: {traceback.format_exc()}")
                    raise
            else:
                logger.error(">>> Failed to open email backend connection")
                raise Exception("Failed to open email backend connection")

            # Close the email connection
            logger.debug(">>> Closing email backend connection")
            email_backend.close()
            logger.debug(">>> Email backend connection closed")

    except Exception as e:
        logger.error(f">>> Error in send_email_f: {str(e)}")
        logger.error(f">>> Full traceback: {traceback.format_exc()}")
        return {"error": str(e)}

    logger.info(">>> send_email_f completed successfully")
    return {"success": "Email sent and logged successfully"}


async def fetch_emails_for_imap_user(imap_user, log_model):
    """
    Asynchronously fetches unseen emails for a specified IMAP user and logs them using the specified model.
    """
    logger.info(f">>> =============== STARTING IMAP FETCH FOR {imap_user} ===============")

    imap_server = settings.IMAP_SERVER
    imap_port = settings.IMAP_PORT
    imap_password = settings.IMAP_PASSWORD
    mail = None

    logger.info(f">>> IMAP Configuration:")
    logger.info(f">>> Server: {imap_server}")
    logger.info(f">>> Port: {imap_port}")
    logger.info(f">>> User: {imap_user}")
    logger.info(f">>> Password length: {len(imap_password) if imap_password else 0}")
    logger.info(f">>> Log model: {log_model.__name__}")
    logger.info(f">>> Environment: {os.environ.get('RENDER', 'local')}")

    try:
        logger.info(f">>> Creating IMAP4_SSL connection to {imap_server}:{imap_port}")
        mail = aioimaplib.IMAP4_SSL(imap_server, imap_port, timeout=30)
        logger.info(f">>> IMAP connection object created: {type(mail)}")

        logger.info(">>> Waiting for server greeting...")
        await mail.wait_hello_from_server()
        logger.info(
            f">>> Server greeting received. Current state: {mail.protocol.state if hasattr(mail, 'protocol') else 'Unknown'}")

        logger.info(f">>> Attempting login for user: {imap_user}")
        login_response = await mail.login(imap_user, imap_password)
        logger.info(f">>> Login response result: {login_response.result}")
        logger.info(f">>> Login response lines: {login_response.lines}")
        logger.info(f">>> State after login attempt: {mail.protocol.state if hasattr(mail, 'protocol') else 'Unknown'}")

        if login_response.result != 'OK':
            logger.error(f">>> LOGIN FAILED! Result: {login_response.result}")
            logger.error(f">>> Error details: {login_response.lines}")
            raise Exception(f"Login failed: {login_response}")

        logger.info(f">>> Login successful! Current state: {mail.protocol.state}")

        logger.info(">>> Selecting inbox...")
        select_response = await mail.select("inbox")
        logger.info(f">>> Inbox select response: {select_response}")
        logger.info(f">>> State after inbox select: {mail.protocol.state}")

        logger.info(">>> Searching for unseen emails...")
        status, messages = await mail.search('UNSEEN')
        logger.info(f">>> Search status: {status}")
        logger.info(f">>> Search messages: {messages}")

        if status != 'OK':
            logger.error(f">>> Search failed with status: {status}")
            return

        if not messages or not messages[0]:
            logger.info(">>> No unseen emails found")
            unseen_emails = []
        else:
            unseen_emails = messages[0].split()

        logger.info(f">>> Found {len(unseen_emails)} new unseen emails for {imap_user}")

        for i, num in enumerate(unseen_emails):
            logger.info(f">>> Processing email {i + 1}/{len(unseen_emails)}")
            try:
                email_id = num.decode('utf-8')
                logger.info(f">>> Fetching email with ID: {email_id}")

                status, data = await mail.fetch(email_id, "(RFC822)")
                logger.debug(f">>> Fetch status: {status}")
                logger.debug(f">>> Fetch data length: {len(data) if data else 0}")

                if status != "OK" or not data or len(data) < 2 or not isinstance(data[1], (bytes, bytearray)):
                    logger.warning(f">>> Failed to fetch email {email_id}. Status: {status}, Data: {type(data)}")
                    continue

                logger.info(f">>> Successfully fetched email with ID: {email_id}, size: {len(data[1])} bytes")
                msg = email.message_from_bytes(data[1])

                # Decode subject
                logger.debug(">>> Decoding email subject...")
                subject_tuple = decode_header(msg.get("Subject", "No Subject"))[0]
                subject, encoding = subject_tuple if isinstance(subject_tuple[0], (bytes, str)) else (
                    'No Subject', None)
                if isinstance(subject, bytes):
                    subject = subject.decode(encoding if encoding else 'utf-8')

                logger.info(f">>> Email Subject: {subject}")

                # Extract sender and recipient information
                logger.debug(">>> Extracting sender and recipient information...")
                sender = parseaddr(msg.get("From"))[1]
                recipient = parseaddr(msg.get("Delivered-To"))[1] or parseaddr(msg.get("To"))[1]

                # Handle forwarded emails by looking for additional headers
                if msg.get("X-Forwarded-To"):
                    recipient = parseaddr(msg.get("X-Forwarded-To"))[1]
                    logger.debug(f">>> Found X-Forwarded-To header: {recipient}")

                # If the recipient is still None, use imap_user as the recipient
                if not recipient:
                    recipient = imap_user
                    logger.debug(f">>> Using imap_user as recipient: {recipient}")

                logger.info(f">>> Sender: {sender}")
                logger.info(f">>> Recipient: {recipient}")

                message = ""
                html_content = ""
                attachments = []
                original_filenames = []

                # Use sync_to_async for find_user_by_email function
                logger.debug(">>> Looking up solicitor firm...")
                solicitor_firm = await sync_to_async(find_user_by_email)(sender)
                logger.debug(f">>> Solicitor firm: {solicitor_firm}")

                message_id = msg.get("Message-ID", "")
                logger.debug(f">>> Message ID: {message_id}")

                logger.debug(">>> Processing email content...")
                if msg.is_multipart():
                    logger.debug(">>> Email is multipart, processing parts...")
                    part_count = 0
                    for part in msg.walk():
                        part_count += 1
                        content_type = part.get_content_type()
                        filename = part.get_filename()
                        logger.debug(f">>> Part {part_count}: Content-Type: {content_type}, Filename: {filename}")

                        if content_type == "text/html":
                            logger.debug(">>> Processing HTML content")
                            html_content += part.get_payload(decode=True).decode('utf-8', errors='replace')
                        elif content_type == "text/plain" and not html_content:
                            logger.debug(">>> Processing plain text content")
                            message += part.get_payload(decode=True).decode('utf-8', errors='replace')

                        if filename:
                            logger.info(f">>> Processing attachment: {filename}")
                            try:
                                unique_filename = f"{uuid.uuid4()}{os.path.splitext(filename)[1]}"
                                file_path = os.path.join(settings.MEDIA_ROOT, 'email_attachments', unique_filename)
                                logger.debug(f">>> Saving attachment to: {file_path}")

                                file_content = part.get_payload(decode=True)
                                async with aiofiles.open(file_path, 'wb') as f:
                                    await f.write(file_content)

                                attachments.append(file_path)
                                original_filenames.append(filename)
                                logger.info(f">>> Attachment saved: {filename} -> {file_path}")
                            except Exception as e:
                                logger.error(f">>> Error saving attachment {filename}: {e}")

                else:
                    logger.debug(">>> Email is not multipart, processing single part...")
                    message = msg.get_payload(decode=True).decode('utf-8', errors='replace')

                # Save the email asynchronously using sync_to_async
                logger.info(">>> Saving email to database...")
                try:
                    email_log = await sync_to_async(log_model.objects.create)(
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
                    logger.info(f">>> Email saved successfully with ID: {email_log.id}")
                except Exception as e:
                    logger.error(f">>> Error saving email to database: {e}")
                    logger.error(f">>> Database save traceback: {traceback.format_exc()}")

            except Exception as e:
                logger.error(f">>> Error processing email with ID {email_id}: {e}")
                logger.error(f">>> Email processing traceback: {traceback.format_exc()}")

    except Exception as e:
        logger.error(f">>> ERROR in fetch_emails_for_imap_user for {imap_user}: {str(e)}")
        logger.error(f">>> Error type: {type(e).__name__}")
        if mail and hasattr(mail, 'protocol'):
            logger.error(f">>> Mail state during error: {mail.protocol.state}")
        logger.error(f">>> Full traceback: {traceback.format_exc()}")

        # Don't try to logout if we're not authenticated
        if mail and hasattr(mail, 'protocol') and mail.protocol.state in ['AUTHENTICATED', 'SELECTED']:
            try:
                logger.info(">>> Attempting logout after error...")
                await mail.logout()
                logger.info(">>> Logout successful after error")
            except Exception as logout_error:
                logger.error(f">>> Logout failed after error: {logout_error}")
        else:
            logger.info(
                f">>> Skipping logout after error - connection state: {mail.protocol.state if mail and hasattr(mail, 'protocol') else 'None'}")

        raise

    finally:
        logger.info(">>> Entering finally block...")
        if mail and hasattr(mail, 'protocol'):
            logger.info(f">>> Final cleanup - Mail state: {mail.protocol.state}")
            if mail.protocol.state in ['AUTHENTICATED', 'SELECTED']:
                try:
                    logger.info(">>> Attempting final logout...")
                    await mail.logout()
                    logger.info(">>> Final logout successful")
                except Exception as e:
                    logger.warning(f">>> Final logout failed: {e}")
            else:
                logger.info(f">>> Skipping final logout - state: {mail.protocol.state}")
        else:
            logger.info(">>> No mail connection to clean up")

        logger.info(f">>> =============== COMPLETED IMAP FETCH FOR {imap_user} ===============")


async def fetch_emails():
    """
    Asynchronously fetches emails for the default IMAP user and for staff users in the "agents" team.
    """
    logger.info(">>> =============== STARTING FETCH_EMAILS ===============")

    try:
        logger.info(f">>> Fetching emails for default IMAP user: {settings.IMAP_USER}")
        await fetch_emails_for_imap_user(settings.IMAP_USER, EmailLog)
        logger.info(">>> Default IMAP user email fetch completed")
    except Exception as e:
        logger.error(f">>> Error fetching emails for default user: {e}")
        logger.error(f">>> Fetch emails error traceback: {traceback.format_exc()}")
        # Re-raise the exception so the scheduler knows it failed
        raise

    logger.info(">>> fetch_emails completed")

    """This part is turned off, because im using forwarders to forward all user related emails into the info inbox"""
    # # Fetch emails for users who are staff and belong to the "agents" team
    # logger.info(">>> Fetching staff users in 'agents' team...")
    # try:
    #     users = await sync_to_async(lambda: list(User.objects.filter(is_staff=True, teams__name="agents")))()
    #     logger.info(f">>> Found {len(users)} staff users in 'agents' team")
    #
    #     # Create a list of tasks for each user
    #     tasks = [
    #         fetch_emails_for_imap_user(user.email, UserEmailLog) for user in users
    #     ]
    #     logger.info(f">>> Created {len(tasks)} fetch tasks")
    #
    #     # Run all the tasks concurrently
    #     await asyncio.gather(*tasks)
    #     logger.info(">>> All user email fetch tasks completed")
    # except Exception as e:
    #     logger.error(f">>> Error fetching emails for staff users: {e}")
    #     logger.error(f">>> Staff users fetch traceback: {traceback.format_exc()}")

# Commented out notification function with logging
# def _send_notification(email_log, message, recipient):
#     """Send a notification to the assigned user when an email log is created, updated, or deleted."""
#     logger.info(f">>> Starting notification send for recipient: {recipient}")
#     try:
#         logger.debug(">>> Creating notification object...")
#         notification = Notification.objects.create(
#             recipient=recipient,
#             text=message,
#             seen=False,
#             created_by=email_log.solicitor_firm,
#             application=None,
#         )
#         logger.info(f">>> Notification created with ID: {notification.id}")
#     except Exception as e:
#         logger.error(f">>> Error creating notification: {e}")
#         logger.error(f">>> Notification creation traceback: {traceback.format_exc()}")
#         return
#
#     try:
#         logger.debug(">>> Getting channel layer...")
#         channel_layer = get_channel_layer()
#         logger.debug(">>> Channel layer obtained.")
#     except Exception as e:
#         logger.error(f">>> Error getting channel layer: {e}")
#         logger.error(f">>> Channel layer traceback: {traceback.format_exc()}")
#         return
#
#     try:
#         logger.debug(">>> Sending notification via channel layer...")
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
#         logger.info(">>> Notification sent successfully via WebSocket.")
#     except Exception as e:
#         logger.error(f">>> Error sending notification via WebSocket: {e}")
#         logger.error(f">>> WebSocket send traceback: {traceback.format_exc()}")
