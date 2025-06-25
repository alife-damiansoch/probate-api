# document_emails/urls.py
from django.urls import path
from .views import (
    EmailCommunicationListView,
    EmailCommunicationDetailView,
    SendEmailView,
    EmailDocumentDownloadView,
    EmailTemplateListView,  # Add this import
)

app_name = 'document_emails'

urlpatterns = [
    # Email communications for a specific application
    path(
        'applications/<int:application_id>/emails/',
        EmailCommunicationListView.as_view(),
        name='email-list-create'
    ),

    # Individual email communication operations
    path(
        'emails/<int:email_id>/',
        EmailCommunicationDetailView.as_view(),
        name='email-detail'
    ),

    # Send email
    path(
        'emails/<int:email_id>/send/',
        SendEmailView.as_view(),
        name='email-send'
    ),

    # Download email document
    path(
        'email-documents/<int:document_id>/download/',
        EmailDocumentDownloadView.as_view(),
        name='email-document-download'
    ),

    # List available email templates
    path(
        'email-templates/',
        EmailTemplateListView.as_view(),
        name='email-templates'
    ),
]
