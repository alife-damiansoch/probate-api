from django.urls import path
from .views import LoanBookDetailView

urlpatterns = [
    path('<int:pk>/', LoanBookDetailView.as_view(), name='loanbook-detail'),
]
