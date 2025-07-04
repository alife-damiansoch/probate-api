# ccr_reporting/urls.py - Fixed to match your URL structure (api/ccr/)
from django.urls import path
from . import views

app_name = 'ccr_reporting'

urlpatterns = [
    # Main submission endpoints
    path('generate/', views.generate_ccr_submission, name='generate_submission'),
    path('preview/', views.ccr_submission_preview, name='submission_preview'),
    path('history/', views.ccr_submission_history, name='submission_history'),

    # File download endpoint
    path('download/', views.download_submission_file, name='download_submission_file'),

    # Testing endpoints
    path('test/sequence/', views.generate_test_sequence, name='generate_test_sequence'),
    path('test/clear/', views.clear_test_submissions, name='clear_test_submissions'),
    path('test/settle/', views.simulate_loan_settlement, name='simulate_loan_settlement'),
]

# Your main urls.py should include this as:
# path('api/ccr/', include('ccr_reporting.urls')),
