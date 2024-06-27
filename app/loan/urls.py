"""url mapping for the Loan api"""

from django.urls import path, include

from rest_framework.routers import DefaultRouter

from loan.views import LoanViewSet

router = DefaultRouter()

router.register('loans', LoanViewSet, basename='loan')

app_name = 'loans'

urlpatterns = [
    path('', include(router.urls)),
]
