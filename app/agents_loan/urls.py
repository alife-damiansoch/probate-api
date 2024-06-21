"""
URL mapping for agents_application Api
"""

from django.urls import path, include

from rest_framework.routers import DefaultRouter

from agents_loan import views

router = DefaultRouter()

router.register('agent_applications', views.ApplicationViewSet, basename='agent_application')

app_name = 'agents_loan'

urlpatterns = [
    path('', include(router.urls)),
    path('agent_applications/document_file/delete/<int:document_id>/',
         views.DocumentDeleteView.as_view(),
         name='agents-document-delete-view'),
    path('agent_applications/document_file/<int:application_id>/',
         views.DocumentUploadAndViewListForApplicationIdView.as_view(),
         name='agent_application-upload-document'),

]
