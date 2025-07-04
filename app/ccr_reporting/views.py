# ccr_reporting/views.py - Fixed version with proper 3-month sequence generation
import os

from django.http import HttpResponse
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from datetime import datetime, timedelta
import zipfile
import io
import calendar

from app import settings
from .services.file_generator import CCRFileGenerator
from .models import CCRSubmission, CCRContractRecord
from agents_loan.permissions import IsStaff


def get_month_end_date(year, month):
    """Get the last day of a given month"""
    last_day = calendar.monthrange(year, month)[1]
    return datetime(year, month, last_day).date()


def add_months(date, months):
    """Add months to a date and return the month-end date"""
    month = date.month
    year = date.year
    month += months

    while month > 12:
        month -= 12
        year += 1

    return get_month_end_date(year, month)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsStaff])
def generate_ccr_submission(request):
    """Generate CCR submission file and return it to frontend with settlement handling"""
    print("=== CCR SUBMISSION REQUEST STARTED ===")
    try:
        data = request.data
        print(f"Request data: {data}")
        print(f"Request method: {request.method}")
        print(f"User: {request.user}")

        # Validate request data
        if not data:
            print("ERROR: No data provided in request body")
            return Response({
                'error': 'No data provided in request body'
            }, status=400)

        # Test mode allows multiple submissions and date manipulation
        test_mode = data.get('test_mode', False)
        print(f"Test mode: {test_mode}")

        # Get reference date
        if 'force_date' in data and test_mode:
            reference_date = datetime.strptime(data['force_date'], '%Y-%m-%d').date()
            print(f"Using force_date: {reference_date}")
        elif 'reference_date' in data:
            reference_date = datetime.strptime(data['reference_date'], '%Y-%m-%d').date()
            print(f"Using reference_date: {reference_date}")
        else:
            today = timezone.now().date()
            reference_date = today.replace(day=1) - timedelta(days=1)
            print(f"Using calculated reference_date: {reference_date}")

        print(f"Final reference date: {reference_date}")

        # Generate CCR submission
        print("Creating CCRFileGenerator...")
        generator = CCRFileGenerator()

        print("Calling generate_monthly_submission...")
        file_content, record_count, summary = generator.generate_monthly_submission(
            reference_date,
            force_test_mode=test_mode
        )

        print(f"Generation completed!")
        print(f"Record count: {record_count}")
        print(f"File content length: {len(file_content) if file_content else 0}")
        print(f"Summary: {summary}")

        if not file_content:
            print("ERROR: No file content generated")
            return Response({
                'error': 'No data to generate - no qualifying loans found',
                'summary': summary,
                'details': {
                    'new_contracts': summary.get('new_contracts', 0),
                    'active_contracts': summary.get('active_contracts', 0),
                    'settled_contracts': summary.get('settled_contracts', 0),
                }
            }, status=400)

        print("Preparing file response...")
        # Prepare file for download
        response = HttpResponse(
            file_content.encode('utf-8'),
            content_type='text/plain'
        )

        provider_code = os.getenv('CCR_PROVIDER_CODE') or getattr(settings, 'CCR_PROVIDER_CODE', 'UNKNOWN')
        timestamp_str = timezone.now().strftime('%Y%m%d%H%M%S')
        filename = f'{provider_code}_CSDF_{timestamp_str}.txt'

        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        response['X-CCR-Record-Count'] = str(record_count)
        response['X-CCR-Reference-Date'] = reference_date.strftime('%Y-%m-%d')
        response['X-CCR-Test-Mode'] = str(test_mode)
        response['X-CCR-Summary'] = str(summary)

        print(f"Returning response with filename: {filename}")
        print("=== CCR SUBMISSION REQUEST COMPLETED SUCCESSFULLY ===")
        return response

    except Exception as e:
        print(f"=== CCR SUBMISSION REQUEST FAILED ===")
        print(f"Error in generate_ccr_submission: {e}")
        import traceback
        traceback.print_exc()
        return Response({
            'error': str(e),
            'test_mode_hint': 'Try adding "test_mode": true to allow multiple submissions'
        }, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsStaff])
def generate_test_sequence(request):
    """
    Generate a sequence of CCR submissions for testing settlement scenarios
    Returns both database records AND file contents for inspection

    POST data:
    {
        "start_date": "2024-01-31",
        "months": 3,
        "return_files": true  // Optional: return file contents for inspection
    }
    """
    print("=== GENERATE_TEST_SEQUENCE STARTED ===")
    try:
        data = request.data

        # Validate input
        if not data.get('start_date'):
            return Response({'error': 'start_date is required'}, status=400)

        start_date = datetime.strptime(data['start_date'], '%Y-%m-%d').date()
        months = data.get('months', 3)
        return_files = data.get('return_files', False)

        print(f"Start date: {start_date}, Months: {months}, Return files: {return_files}")

        generator = CCRFileGenerator()
        results = []
        files = []  # Store file contents if requested

        current_date = start_date
        for i in range(months):
            try:
                print(f"\n--- Generating month {i + 1}/{months} for date {current_date} ---")

                file_content, record_count, summary = generator.generate_monthly_submission(
                    current_date,
                    force_test_mode=True
                )

                month_result = {
                    'month': i + 1,
                    'reference_date': current_date.isoformat(),
                    'record_count': record_count,
                    'summary': summary,
                    'success': True
                }

                # If file content was generated and files are requested
                if file_content and return_files:
                    files.append({
                        'month': i + 1,
                        'filename': f'ccr_test_month_{i + 1}_{current_date.strftime("%Y%m%d")}.txt',
                        'content': file_content,
                        'size': len(file_content)
                    })
                    print(f"Added file for month {i + 1}: {len(file_content)} characters")

                results.append(month_result)
                print(f"Month {i + 1} completed: {record_count} records")

                # Calculate next month end date properly
                current_date = add_months(current_date, 1)
                print(f"Next date will be: {current_date}")

            except Exception as e:
                print(f"Error in month {i + 1}: {e}")
                import traceback
                traceback.print_exc()
                results.append({
                    'month': i + 1,
                    'reference_date': current_date.isoformat(),
                    'error': str(e),
                    'success': False
                })
                # Don't break on error, continue with next month
                current_date = add_months(current_date, 1)

        response_data = {
            'success': True,
            'total_months_processed': len([r for r in results if r.get('success')]),
            'total_months_requested': months,
            'results': results
        }

        # Add files if requested
        if return_files and files:
            response_data['files'] = files
            response_data['download_info'] = {
                'total_files': len(files),
                'total_size': sum(f['size'] for f in files),
                'note': 'File contents included in response for inspection'
            }

        print(f"\n=== GENERATE_TEST_SEQUENCE COMPLETED ===")
        print(f"Processed {len(results)} months, {len(files)} files generated")
        return Response(response_data)

    except Exception as e:
        print(f"=== GENERATE_TEST_SEQUENCE FAILED ===")
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return Response({
            'error': str(e)
        }, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsStaff])
def simulate_loan_settlement(request):
    """
    Simulate settling a loan for testing CCR settlement reporting

    POST data:
    {
        "loan_id": 123,
        "settlement_date": "2025-01-15"
    }
    """
    print("=== SIMULATE_LOAN_SETTLEMENT STARTED ===")
    try:
        data = request.data
        loan_id = data.get('loan_id')
        settlement_date_str = data.get('settlement_date')

        if not loan_id:
            return Response({'error': 'loan_id is required'}, status=400)
        if not settlement_date_str:
            return Response({'error': 'settlement_date is required'}, status=400)

        settlement_date = datetime.strptime(settlement_date_str, '%Y-%m-%d').date()
        print(f"Simulating settlement of loan {loan_id} on {settlement_date}")

        # Import here to avoid circular imports
        from loanbook.models import Loan

        try:
            loan = Loan.objects.get(id=loan_id)
        except Loan.DoesNotExist:
            return Response({'error': f'Loan {loan_id} not found'}, status=404)

        # Check if loan is already settled
        if loan.is_settled:
            return Response({
                'error': f'Loan {loan_id} is already settled on {loan.settled_date}',
                'current_status': 'settled'
            }, status=400)

        # Simulate settlement
        loan.is_settled = True
        loan.settled_date = settlement_date
        loan.save()

        print(f"Loan {loan_id} marked as settled on {settlement_date}")

        return Response({
            'success': True,
            'message': f'Simulated settlement of loan {loan_id} on {settlement_date}',
            'loan_id': loan_id,
            'settlement_date': settlement_date.isoformat(),
            'next_steps': 'Run CCR generation for the settlement month to see final reporting'
        })

    except Exception as e:
        print(f"=== SIMULATE_LOAN_SETTLEMENT FAILED ===")
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return Response({
            'error': str(e)
        }, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsStaff])
def ccr_submission_preview(request):
    """
    Preview CCR submission data without generating file - includes settlement data
    """
    print("=== CCR_SUBMISSION_PREVIEW STARTED ===")
    try:
        reference_date_str = request.GET.get('reference_date')
        test_date_str = request.GET.get('test_date')  # For testing with custom dates

        if test_date_str:
            reference_date = datetime.strptime(test_date_str, '%Y-%m-%d').date()
            print(f"Using test_date: {reference_date}")
        elif reference_date_str:
            reference_date = datetime.strptime(reference_date_str, '%Y-%m-%d').date()
            print(f"Using reference_date: {reference_date}")
        else:
            today = timezone.now().date()
            reference_date = today.replace(day=1) - timedelta(days=1)
            print(f"Using calculated reference_date: {reference_date}")

        generator = CCRFileGenerator()
        preview_data = generator.get_submission_preview(reference_date)

        print(f"Preview completed for {reference_date}")
        print(f"Total records would be: {preview_data['total_records']}")

        return Response({
            'success': True,
            'reference_date': reference_date.isoformat(),
            'preview': preview_data,
            'breakdown': {
                'new_loans': preview_data['new_contracts']['count'],
                'active_loans': preview_data['active_contracts']['count'],
                'settled_loans': preview_data['settled_contracts']['count'],
                'total_records': preview_data['total_records']
            },
            'test_dates_available': {
                'today': timezone.now().date().isoformat(),
                'last_month_end': (timezone.now().date().replace(day=1) - timedelta(days=1)).isoformat(),
                'custom_suggestion': '2024-01-31'
            }
        })

    except Exception as e:
        print(f"=== CCR_SUBMISSION_PREVIEW FAILED ===")
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return Response({
            'error': str(e)
        }, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsStaff])
def ccr_submission_history(request):
    """Get history of CCR submissions with test filtering and settlement tracking"""
    print("=== CCR_SUBMISSION_HISTORY STARTED ===")

    try:
        show_test = request.GET.get('show_test', 'true').lower() == 'true'
        print(f"Show test submissions: {show_test}")

        submissions_query = CCRSubmission.objects.all()
        if not show_test:
            submissions_query = submissions_query.filter(is_test_submission=False)

        submissions = submissions_query.order_by('-reference_date')[:20]
        print(f"Found {submissions.count()} submissions")

        submission_data = []
        for submission in submissions:
            # Get breakdown of submission types by analyzing CCR records updated on this date
            from django.db.models import Q

            # Count contracts reported in this submission
            new_contracts = CCRContractRecord.objects.filter(
                first_reported_date=submission.reference_date
            ).count()

            # Count active updates (existing contracts updated)
            active_updates = CCRContractRecord.objects.filter(
                last_reported_date=submission.reference_date,
                first_reported_date__lt=submission.reference_date,
                is_closed_in_ccr=False
            ).count()

            # Count settlements (contracts closed in this submission)
            settlements = CCRContractRecord.objects.filter(
                closed_date=submission.reference_date,
                is_closed_in_ccr=True
            ).count()

            breakdown = {
                'new': new_contracts,
                'updates': active_updates,
                'settlements': settlements,
            }

            submission_data.append({
                'id': submission.id,
                'reference_date': submission.reference_date,
                'generated_at': submission.generated_at,
                'total_records': submission.total_records,
                'status': submission.status,
                'file_path': submission.file_path,
                'is_test': submission.is_test_submission,
                'test_notes': submission.test_notes,
                'breakdown': breakdown
            })

        print("=== CCR_SUBMISSION_HISTORY COMPLETED ===")
        return Response({
            'submissions': submission_data,
            'showing_test_submissions': show_test
        })

    except Exception as e:
        print(f"=== CCR_SUBMISSION_HISTORY FAILED ===")
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return Response({
            'error': str(e)
        }, status=500)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated, IsStaff])
def clear_test_submissions(request):
    """Clear all test submissions and related CCR contract records - useful for testing"""
    print("=== CLEAR_TEST_SUBMISSIONS STARTED ===")
    try:
        # Get test submissions
        test_submissions = CCRSubmission.objects.filter(is_test_submission=True)
        test_submission_count = test_submissions.count()
        print(f"Found {test_submission_count} test submissions")

        # Get CCR contract records that were created during test submissions
        # We'll identify these by finding records where first_reported_date matches test submission dates
        test_submission_dates = list(test_submissions.values_list('reference_date', flat=True))

        ccr_records_to_delete = CCRContractRecord.objects.filter(
            first_reported_date__in=test_submission_dates
        )
        ccr_record_count = ccr_records_to_delete.count()
        print(f"Found {ccr_record_count} CCR contract records linked to test submissions")

        # Reset ccr_reported flag on applicants that were only reported in test submissions
        from loanbook.models import LoanBook

        # Get loanbooks associated with test CCR records
        test_loanbooks = [record.loanbook for record in ccr_records_to_delete]
        applicants_to_reset = []

        for loanbook in test_loanbooks:
            try:
                applicant = loanbook.loan.application.applicants.first()
                if applicant and getattr(applicant, 'ccr_reported', False):
                    # Check if this applicant has any non-test CCR records
                    non_test_records = CCRContractRecord.objects.filter(
                        loanbook__loan__application__applicants=applicant
                    ).exclude(first_reported_date__in=test_submission_dates)

                    if not non_test_records.exists():
                        applicants_to_reset.append(applicant)
            except Exception as e:
                print(f"Error checking applicant for loanbook {loanbook.id}: {e}")
                continue

        # Delete in proper order
        print(f"Deleting {ccr_record_count} CCR contract records...")
        ccr_records_to_delete.delete()

        print(f"Deleting {test_submission_count} test submissions...")
        test_submissions.delete()

        # Reset applicant flags
        applicants_reset_count = 0
        for applicant in applicants_to_reset:
            applicant.ccr_reported = False
            applicant.save()
            applicants_reset_count += 1

        message = f'Cleared {test_submission_count} test submissions, {ccr_record_count} CCR contract records, and reset {applicants_reset_count} applicant flags'
        print(f"=== CLEAR_TEST_SUBMISSIONS COMPLETED ===")
        print(message)

        return Response({
            'success': True,
            'deleted_submissions': test_submission_count,
            'deleted_ccr_records': ccr_record_count,
            'reset_applicants': applicants_reset_count,
            'message': message
        })

    except Exception as e:
        print(f"=== CLEAR_TEST_SUBMISSIONS FAILED ===")
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return Response({
            'error': str(e)
        }, status=500)


# Updated download view that handles test data properly

@api_view(['POST'])
@permission_classes([IsAuthenticated, IsStaff])
def download_submission_file(request):
    """
    Download an existing submission file or regenerate if missing
    Handles both production and test data properly
    """
    print("=== DOWNLOAD_SUBMISSION_FILE STARTED ===")
    try:
        submission_id = request.data.get('submission_id')
        if not submission_id:
            return Response({'error': 'submission_id is required'}, status=400)

        try:
            submission = CCRSubmission.objects.get(id=submission_id)
        except CCRSubmission.DoesNotExist:
            return Response({'error': 'Submission not found'}, status=404)

        print(f"Attempting to download file for submission {submission_id} ({submission.reference_date})")
        print(f"Submission is_test_submission: {submission.is_test_submission}")

        # First, try to download existing file if it exists
        if submission.file_path and os.path.exists(submission.file_path):
            print(f"Found existing file at: {submission.file_path}")

            try:
                with open(submission.file_path, 'r', encoding='utf-8') as file:
                    file_content = file.read()

                # Extract filename from path or create a proper one
                filename = os.path.basename(submission.file_path)
                if not filename or filename == '':
                    provider_code = os.getenv('CCR_PROVIDER_CODE') or getattr(settings, 'CCR_PROVIDER_CODE', 'UNKNOWN')
                    filename = f'{provider_code}_CSDF_{submission.reference_date.strftime("%Y%m%d")}.txt'

                # Return existing file
                response = HttpResponse(
                    file_content.encode('utf-8'),
                    content_type='text/plain'
                )

                response['Content-Disposition'] = f'attachment; filename="{filename}"'
                response['X-CCR-Record-Count'] = str(submission.total_records)
                response['X-CCR-Reference-Date'] = submission.reference_date.strftime('%Y-%m-%d')
                response['X-CCR-Test-Mode'] = str(submission.is_test_submission)
                response['X-CCR-Filename'] = filename
                response['X-CCR-Source'] = 'existing_file'

                # Add CORS headers
                response[
                    'Access-Control-Expose-Headers'] = 'Content-Disposition, X-CCR-Record-Count, X-CCR-Reference-Date, X-CCR-Test-Mode, X-CCR-Filename, X-CCR-Source'

                print(f"Successfully downloaded existing file: {filename}")
                print("=== DOWNLOAD_SUBMISSION_FILE COMPLETED (EXISTING) ===")
                return response

            except Exception as file_error:
                print(f"Error reading existing file: {file_error}")
                # Fall through to regeneration

        # File not found, need to regenerate
        print(f"File not found, regenerating for submission {submission_id}")
        print(f"Submission was test mode: {submission.is_test_submission}")

        # Try regeneration using generator (works for both test and production)
        print("=== TRYING GENERATOR REGENERATION ===")
        generator = CCRFileGenerator()

        try:
            # Force test mode if this was a test submission
            force_test = submission.is_test_submission

            file_content, record_count, summary = generator.generate_file_content_only(
                submission.reference_date,
                force_test_mode=force_test
            )

            if file_content and record_count > 0:
                print(f"Successfully regenerated file content: {record_count} records")

                # Create proper filename
                provider_code = os.getenv('CCR_PROVIDER_CODE') or getattr(settings, 'CCR_PROVIDER_CODE', 'UNKNOWN')
                timestamp_str = timezone.now().strftime('%Y%m%d%H%M%S')
                filename = f'{provider_code}_CSDF_{timestamp_str}_regenerated.txt'

                # Return regenerated file
                response = HttpResponse(
                    file_content.encode('utf-8'),
                    content_type='text/plain'
                )

                response['Content-Disposition'] = f'attachment; filename="{filename}"'
                response['X-CCR-Record-Count'] = str(record_count)
                response['X-CCR-Reference-Date'] = submission.reference_date.strftime('%Y-%m-%d')
                response['X-CCR-Test-Mode'] = str(force_test)
                response['X-CCR-Filename'] = filename
                response['X-CCR-Source'] = 'regenerated'

                # Add CORS headers
                response[
                    'Access-Control-Expose-Headers'] = 'Content-Disposition, X-CCR-Record-Count, X-CCR-Reference-Date, X-CCR-Test-Mode, X-CCR-Filename, X-CCR-Source'

                print(f"File regenerated and downloaded: {filename}")
                print("=== DOWNLOAD_SUBMISSION_FILE COMPLETED (REGENERATED) ===")
                return response
            else:
                print("Generator returned no content")

        except Exception as generation_error:
            print(f"Generator regeneration failed: {generation_error}")
            import traceback
            traceback.print_exc()

        # Final fallback - create basic file from submission data
        print("=== CREATING FALLBACK FILE ===")
        provider_code = os.getenv('CCR_PROVIDER_CODE') or getattr(settings, 'CCR_PROVIDER_CODE', 'UNKNOWN')

        file_content = f"# CCR Submission File (Fallback)\n"
        file_content += f"# Provider: {provider_code}\n"
        file_content += f"# Reference Date: {submission.reference_date}\n"
        file_content += f"# Original Record Count: {submission.total_records}\n"
        file_content += f"# Test Submission: {submission.is_test_submission}\n"
        file_content += f"# Status: Could not regenerate original content\n\n"
        file_content += f"H|{provider_code}|{submission.reference_date.strftime('%Y%m%d')}|CSDF|1.0\n"
        file_content += f"# Fallback file - original contained {submission.total_records} records\n"
        file_content += f"T|{submission.total_records}\n"

        filename = f'{provider_code}_CSDF_fallback_{submission.reference_date.strftime("%Y%m%d")}.txt'

        response = HttpResponse(
            file_content.encode('utf-8'),
            content_type='text/plain'
        )

        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        response['X-CCR-Record-Count'] = str(submission.total_records)
        response['X-CCR-Reference-Date'] = submission.reference_date.strftime('%Y-%m-%d')
        response['X-CCR-Test-Mode'] = str(submission.is_test_submission)
        response['X-CCR-Filename'] = filename
        response['X-CCR-Source'] = 'fallback'

        response[
            'Access-Control-Expose-Headers'] = 'Content-Disposition, X-CCR-Record-Count, X-CCR-Reference-Date, X-CCR-Test-Mode, X-CCR-Filename, X-CCR-Source'

        print(f"Returning fallback file: {filename}")
        print("=== DOWNLOAD_SUBMISSION_FILE COMPLETED (FALLBACK) ===")
        return response

    except Exception as e:
        print(f"=== DOWNLOAD_SUBMISSION_FILE FAILED ===")
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return Response({
            'error': str(e)
        }, status=500)
