"""
URL mapping for agents_application Api
"""

from django.urls import path, include

from rest_framework.routers import DefaultRouter

from agents_loan import views
from agents_loan.views import DownloadFileView, NewApplicationViewSet

router = DefaultRouter()

router.register('applications/agent_applications', views.AgentApplicationViewSet, basename='agent_application')

app_name = 'agents_loan'

urlpatterns = [
    path('', include(router.urls)),
    path('applications/agent_applications/document_file/delete/<int:document_id>/',
         views.AgentDocumentDeleteView.as_view(),
         name='agents-document-delete-view'),
    path('applications/agent_applications/document_file/<int:application_id>/',
         views.AgentDocumentUploadAndViewListForApplicationIdView.as_view(),
         name='agent_application-upload-document'),
    path('applications/agent_applications/document_patch/<int:document_id>/', views.AgentDocumentPatchView.as_view(),
         name='agents-document-patch-view'),
    path('applications/agent_applications/document_file/download/<str:filename>/', DownloadFileView.as_view(),
         name='download-file'),
    # NewApplicationViewSet URLs
    path('applications/agent_applications/new_applications/list/',
         NewApplicationViewSet.as_view({'get': 'list_new'}),
         name='new-applications-list'),
    path('applications/agent_applications/new_applications/<int:pk>/mark-seen/',
         NewApplicationViewSet.as_view({'patch': 'mark_seen'}),
         name='new-applications-mark-seen'),
]
