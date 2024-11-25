# communications/urls.py
from django.urls import path
from .views import (SendEmailViewSet, AttachmentDownloadView, DeleteAttachmentView, ReplyToEmailViewSet,
    # UserEmailViewSet
                    )

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

"""NOT IN USE FOR THE MOMENT USER EMAILS TURNED OFF FOR THE MOMENT"""

# urlpatterns += [
#     path('communications/user_emails/list/', UserEmailViewSet.as_view({'get': 'list'}), name='user_email_list'),
#     path('communications/user_emails/count-unseen/', UserEmailViewSet.as_view({'get': 'count_unseen'}),
#          name='user_email_count_unseen'),
#     path('communications/user_emails/send_to_recipients/',
#          UserEmailViewSet.as_view({'post': 'send_email_to_recipients'}), name='send_user_email_to_recipients'),
#     path('communications/user_emails/update_application/<int:pk>/',
#          UserEmailViewSet.as_view({'patch': 'update_application'}), name='update_user_application'),
#     path('communications/user_emails/update_seen/<int:pk>/', UserEmailViewSet.as_view({'patch': 'update_seen'}),
#          name='update_user_seen'),
#     path('communications/user_emails/reply/', UserEmailViewSet.as_view({'post': 'reply_to_email'}),
#          name='reply_to_user_email'),
# ]
