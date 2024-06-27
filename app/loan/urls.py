"""url mapping for the Loan api"""

from django.urls import path, include

from rest_framework.routers import DefaultRouter

from loan.views import LoanViewSet, TransactionViewSet, LoanExtensionViewSet

router = DefaultRouter()

router.register('loans/loans', LoanViewSet, basename='loan')
router.register('loans/transactions', TransactionViewSet, basename='transaction')
router.register('loans/loan_extensions', LoanExtensionViewSet, basename='loan_extension')

app_name = 'loans'

urlpatterns = [
    path('', include(router.urls)),
]
