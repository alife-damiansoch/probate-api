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
]
