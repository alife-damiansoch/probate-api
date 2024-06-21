"""
URL mapping for solicitors_application Api
"""

from django.urls import path, include

from rest_framework.routers import DefaultRouter

from solicitors_loan import views

router = DefaultRouter()

router.register('solicitor_applications', views.ApplicationViewSet, basename='solicitor_application')

app_name = 'solicitors_loan'

urlpatterns = [
    path('', include(router.urls)),
    path('solicitor_applications/document_file/delete/<int:document_id>/', views.DocumentDeleteView.as_view(),
         name='solicitor-document-delete-view'),
    path('solicitor_applications/document_file/<int:application_id>/',
         views.DocumentUploadAndViewListForApplicationIdView.as_view(),
         name='solicitor_application-upload-document'),

]
