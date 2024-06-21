"""
URL mapping for loan_application Api
"""

from django.urls import path, include

from rest_framework.routers import DefaultRouter

from solicitors_loan import views

router = DefaultRouter()

router.register('solicitor_applications', views.ApplicationViewSet, basename='solicitor_application')

app_name = 'solicitors_loan'

urlpatterns = [
    path('', include(router.urls)),
    path('solicitor_application/<int:application_id>/upload-document/',
         views.DocumentUploadAndViewListForApplicationIdView.as_view(),
         name='solicitor_application-upload-document'),
    path('solicitor_application/<int:document_id>/delete-document', views.DocumentDeleteView.as_view(),
         name='document-delete-view'),
]
