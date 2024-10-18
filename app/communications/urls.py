# communications/urls.py
from django.urls import path
from .views import SendEmailViewSet, AttachmentDownloadView, DeleteAttachmentView, ReplyToEmailViewSet

app_name = 'communications'

# Define custom URL patterns for only the specified endpoints
urlpatterns = [
    path('communications/list/', SendEmailViewSet.as_view({'get': 'list'}), name='email_list'),
    path('communications/count-unseen_info_email/', SendEmailViewSet.as_view({'get': 'count_unseen'}),
         name='email_count_unseen'),
    path('communications/list_by_solicitor_firm/', SendEmailViewSet.as_view({'get': 'list_by_solicitor_firm'}),
         name='email_list_by_solicitor_firm'),
    path('communications/send_with_application/', SendEmailViewSet.as_view({'post': 'send_email_with_application'}),
         name='send_email_with_application'),
    path('communications/send_to_recipients/', SendEmailViewSet.as_view({'post': 'send_email_to_recipients'}),
         name='send_email_to_recipients'),
    path('communications/reply/', ReplyToEmailViewSet.as_view({'post': 'reply_to_email'}), name='reply_to_email'),
    path('communications/update_application_id/<int:pk>/', SendEmailViewSet.as_view({'patch': 'update_application'}),
         name='update_application'),
    path('communications/update_seen/<int:pk>/', SendEmailViewSet.as_view({'patch': 'update_seen'}),
         name='update_seen'),

    path('communications/download_attachment/<int:email_id>/<str:filename>/', AttachmentDownloadView.as_view(),
         name='download_attachment'),
    path('communications/delete_attachment/<int:email_id>/<str:filename>/', DeleteAttachmentView.as_view(),
         name='delete_attachment'),
]
