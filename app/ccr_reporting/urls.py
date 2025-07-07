# ccr_reporting/urls.py - Enhanced with status management endpoints
from django.urls import path
from . import views

app_name = 'ccr_reporting'

urlpatterns = [
    # Main submission endpoints
    path('generate/', views.generate_ccr_submission, name='generate_submission'),
    path('preview/', views.ccr_submission_preview, name='submission_preview'),
    path('history/', views.ccr_submission_history_enhanced, name='submission_history'),

    # File download endpoint
    path('download/', views.download_submission_file, name='download_submission_file'),

    # Status management endpoints
    path('status/update/', views.update_submission_status, name='update_submission_status'),
    path('submission/<int:submission_id>/', views.get_submission_details, name='get_submission_details'),
    path('response/upload/', views.upload_ccr_response, name='upload_ccr_response'),

    # Error management endpoints
    path('errors/add/', views.add_error_record, name='add_error_record'),
    path('errors/resolve/', views.resolve_error_record, name='resolve_error_record'),

    # Testing endpoints
    path('test/sequence/', views.generate_test_sequence, name='generate_test_sequence'),
    path('test/clear/', views.clear_test_submissions, name='clear_test_submissions'),
    path('test/settle/', views.simulate_loan_settlement, name='simulate_loan_settlement'),
]

# Your main urls.py should include this as:
# path('api/ccr/', include('ccr_reporting.urls')),
