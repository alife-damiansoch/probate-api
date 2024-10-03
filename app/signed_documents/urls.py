# signed_documents/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SignedDocumentUploadView, SignedDocumentLogListView, \
    SignedDocumentLogByApplicationView, SignedDocumentLogByFilePathView  # Import the necessary views

# Create a router (for viewsets if any in the future)
router = DefaultRouter()

# Optional: Register ViewSets with the router (useful if you plan to add viewsets in the future)
# Example: router.register(r'signed-documents', SignedDocumentViewSet, basename='signed-document')

app_name = 'signed_documents'

# Define the urlpatterns for your app
urlpatterns = [
    path('', include(router.urls)),  # Include router URLs (empty in this case)
    path('upload/<int:application_id>/', SignedDocumentUploadView.as_view(), name='signed_document_upload'),
    # Add new URLs for listing SignedDocumentLog entries
    path('logs/', SignedDocumentLogListView.as_view(), name='signed_document_log_list'),
    path('logs/<int:application_id>/', SignedDocumentLogByApplicationView.as_view(),
         name='signed_document_log_by_application'),
    path('logs/file/<str:file_name>/', SignedDocumentLogByFilePathView.as_view(), name='signed_document_log_by_file')
]
