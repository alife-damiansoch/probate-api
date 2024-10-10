# communications/urls.py
from django.urls import path
from .views import SendEmailViewSet, AttachmentDownloadView, DeleteAttachmentView

app_name = 'communications'

# Define custom URL patterns for only the specified endpoints
urlpatterns = [
    path('communications/list/', SendEmailViewSet.as_view({'get': 'list'}), name='email_list'),
    path('communications/send_email/', SendEmailViewSet.as_view({'post': 'send_email'}), name='send_email'),
    path('communications/download_attachment/<int:email_id>/<str:filename>/', AttachmentDownloadView.as_view(),
         name='download_attachment'),
    path('communications/delete_attachment/<int:email_id>/<str:filename>/', DeleteAttachmentView.as_view(),
         name='delete_attachment'),
]
