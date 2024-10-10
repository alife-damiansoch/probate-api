# communications/urls.py
from django.urls import path
from .views import SendEmailViewSet, AttachmentDownloadView, DeleteAttachmentView

app_name = 'communications'

# Define custom URL patterns for only the specified endpoints
urlpatterns = [
    path('communications/list/', SendEmailViewSet.as_view({'get': 'list'}), name='email_list'),
    path('communications/send_with_application/', SendEmailViewSet.as_view({'post': 'send_email_with_application'}),
         name='send_email_with_application'),
    path('communications/send_to_recipients/', SendEmailViewSet.as_view({'post': 'send_email_to_recipients'}),
         name='send_email_to_recipients'),
    path('communications/download_attachment/<int:email_id>/<str:filename>/', AttachmentDownloadView.as_view(),
         name='download_attachment'),
    path('communications/delete_attachment/<int:email_id>/<str:filename>/', DeleteAttachmentView.as_view(),
         name='delete_attachment'),
]
