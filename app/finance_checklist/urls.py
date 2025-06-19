# urls.py
from django.urls import path
from . import views

app_name = 'finance_checklist'

urlpatterns = [
    # Get checklist for a specific loan
    path('loan/<int:loan_id>/checklist/',
         views.LoanChecklistView.as_view(),
         name='loan_checklist'),

    # Submit checklist for a specific loan
    path('loan/<int:loan_id>/checklist/submit/',
         views.SubmitLoanChecklistView.as_view(),
         name='submit_loan_checklist'),

    # Get quick status of loan checklist
    path('loan/<int:loan_id>/checklist/status/',
         views.LoanChecklistStatusView.as_view(),
         name='loan_checklist_status'),

    # Get current checklist configuration and items
    path('checklist/config/',
         views.ChecklistConfigurationView.as_view(),
         name='checklist_config'),

    # Get list of loans requiring checklist completion
    path('loans/requiring-checklist/',
         views.LoansRequiringChecklistView.as_view(),
         name='loans_requiring_checklist'),
]
