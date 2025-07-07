# ccr_reporting/services/file_generator.py - Complete version with CCRContractSubmission tracking
from datetime import datetime
from django.conf import settings
from .data_collector import CCRDataCollector
from .ccr_formatter import CCRFileFormatter
from ..models import CCRSubmission, CCRContractRecord, CCRContractSubmission


class CCRFileGenerator:
    """Generate CCR submission files with correct onboarding/tracking."""

    def __init__(self):
        self.collector = CCRDataCollector()
        self.formatter = CCRFileFormatter()

    def generate_monthly_submission(self, reference_date, force_test_mode=False, create_submission=True):
        """Generate monthly CCR submission file with realistic settlement testing in month 3"""
        print(f"=== GENERATE_MONTHLY_SUBMISSION ===")
        print(f"Reference date: {reference_date}")
        print(f"Force test mode: {force_test_mode}")
        print(f"Create submission: {create_submission}")

        is_test_mode = getattr(settings, 'CCR_TEST_MODE', False) or force_test_mode
        print(f"Test mode: {is_test_mode}")

        # Determine if this is regeneration (not creating submission)
        is_regeneration = not create_submission
        print(f"Is regeneration: {is_regeneration}")

        # Only check for existing submission if we're going to create one
        if create_submission and not is_test_mode:
            existing_submission = CCRSubmission.objects.filter(reference_date=reference_date).first()
            if existing_submission:
                raise ValueError(f'CCR submission already exists for {reference_date}')

        # Get loanbooks with regeneration-aware logic
        if is_regeneration:
            print("Using regeneration mode for data collection...")
            new_loanbooks = self.collector.get_new_loanbooks(reference_date, ignore_already_reported=True)
            active_loanbooks = self.collector.get_active_loanbooks(reference_date, for_regeneration=True)
            settled_loanbooks = self.collector.get_settled_loanbooks(reference_date, for_regeneration=True)
        else:
            print("Using normal mode for data collection...")
            new_loanbooks = self.collector.get_new_loanbooks(reference_date)
            active_loanbooks = self.collector.get_active_loanbooks(reference_date)
            settled_loanbooks = self.collector.get_settled_loanbooks(reference_date)

        print(
            f"Found {len(new_loanbooks)} new, {len(active_loanbooks)} active, {len(settled_loanbooks)} settled contracts")

        # *** MONTH 3 SETTLEMENT SIMULATION FOR TEST MODE ***
        is_month_3_test = (
                is_test_mode and
                reference_date.month == 9 and
                reference_date.year == 2025 and
                len(active_loanbooks) > 0
        )

        if is_month_3_test:
            print(f"*** MONTH 3 SETTLEMENT SIMULATION ACTIVATED ***")
            print(f"Moving {len(active_loanbooks)} active loans to settled_loanbooks for realistic testing")
            settled_loanbooks = list(settled_loanbooks) + list(active_loanbooks)
            active_loanbooks = []
            print(f"After simulation: {len(active_loanbooks)} active, {len(settled_loanbooks)} settled")

        submission_lines = []
        applicants_reported_this_file = set()

        # --- HEADER
        if new_loanbooks or active_loanbooks or settled_loanbooks:
            header = self.formatter.create_file_header(reference_date)
            submission_lines.append(header)
            print("Added header")

        # Create submission record first if needed (we'll need it for tracking)
        submission = None
        if create_submission:
            submission = CCRSubmission.objects.create(
                reference_date=reference_date,
                file_path=f'ccr_submission_{reference_date.strftime("%Y%m%d")}.txt',
                total_records=0,  # Will update at the end
                status='GENERATED',
                is_test_submission=is_test_mode
            )
            print(f"Created submission record: {submission.id}")

        # --- Onboard new applicants (ID record only, if never reported to CCR)
        for loanbook in new_loanbooks:
            try:
                applicant = loanbook.loan.application.applicants.first()
                if not applicant:
                    print(f"Warning: No applicant found for loanbook {loanbook.id}")
                    continue

                # For regeneration, we need to check if this applicant was reported in the original submission
                should_add_id = False
                if is_regeneration:
                    # For regeneration, add ID if this was a new loanbook in the original submission
                    # Check if the CCR record was first reported on this date
                    if hasattr(loanbook, 'ccr_record') and loanbook.ccr_record.first_reported_date == reference_date:
                        should_add_id = True
                else:
                    # Normal mode: add ID if never reported
                    should_add_id = not getattr(applicant, 'ccr_reported', False)

                if should_add_id and applicant.id not in applicants_reported_this_file:
                    id_line = self.formatter.format_id_line(self.collector.get_personal_info(applicant), reference_date)
                    submission_lines.append(id_line)
                    applicants_reported_this_file.add(applicant.id)
                    print(f"Added ID record for applicant {applicant.id}")

                    # Only mark applicant as reported if we're creating a submission
                    if create_submission:
                        applicant.ccr_reported = True
                        applicant.save()

                # Handle CCR record creation/updating
                if create_submission:
                    ccr_record, created = CCRContractRecord.objects.get_or_create(
                        loanbook=loanbook,
                        defaults={
                            'ccr_contract_id': loanbook.id,
                            'first_reported_date': reference_date,
                            'last_reported_date': reference_date,
                        }
                    )
                    if not created:
                        ccr_record.last_reported_date = reference_date
                        ccr_record.save()

                    print(f"Updated CCR record for loanbook {loanbook.id}")

                    # Create CCRContractSubmission tracking record
                    CCRContractSubmission.objects.create(
                        contract_record=ccr_record,
                        submission=submission,
                        submission_type='NEW'
                    )
                    print(f"Created NEW contract submission tracking for loanbook {loanbook.id}")

            except Exception as e:
                print(f"Error processing new loanbook {loanbook.id}: {e}")
                continue

        # --- CI records for all contracts active or settling this month
        all_reporting_loanbooks = []
        all_reporting_loanbooks.extend(active_loanbooks)
        all_reporting_loanbooks.extend(settled_loanbooks)

        # Remove duplicates based on loanbook ID
        seen_ids = set()
        unique_loanbooks = []
        for lb in all_reporting_loanbooks:
            if lb.id not in seen_ids:
                unique_loanbooks.append(lb)
                seen_ids.add(lb.id)

        print(f"Processing {len(unique_loanbooks)} unique contracts for CI records")

        for loanbook in unique_loanbooks:
            try:
                # Only output CI if contract is active in this period
                if loanbook.created_at.date() <= reference_date:

                    # Determine if this is an active update or settlement
                    is_settlement = loanbook in settled_loanbooks or is_month_3_test
                    submission_type = 'SETTLEMENT' if is_settlement else 'UPDATE'

                    # *** OVERRIDE LOAN DATA FOR MONTH 3 SETTLEMENT SIMULATION ***
                    if is_month_3_test:
                        print(f"*** OVERRIDING LOAN DATA FOR SETTLEMENT SIMULATION ***")
                        settlement_date = reference_date.replace(day=15)
                        original_is_settled = loanbook.loan.is_settled
                        original_settled_date = getattr(loanbook.loan, 'settled_date', None)

                        loanbook.loan.is_settled = True
                        loanbook.loan.settled_date = settlement_date
                        credit_info = self.collector.get_credit_info(loanbook, reference_date)

                        # Restore original values
                        loanbook.loan.is_settled = original_is_settled
                        loanbook.loan.settled_date = original_settled_date

                        print(f"Generated credit_info with settlement simulation:")
                        print(f"  contract_phase: {credit_info.get('contract_phase')}")
                        print(f"  credit_status: {credit_info.get('credit_status')}")
                    else:
                        credit_info = self.collector.get_credit_info(loanbook, reference_date)

                    ci_line = self.formatter.format_ci_line(credit_info, reference_date)
                    submission_lines.append(ci_line)
                    print(
                        f"Added CI record for loanbook {loanbook.id}, phase: {credit_info['contract_phase']}, type: {submission_type}")

                    # Handle CCR record updating and tracking
                    if create_submission:
                        ccr_record, created = CCRContractRecord.objects.get_or_create(
                            loanbook=loanbook,
                            defaults={
                                'ccr_contract_id': loanbook.id,
                                'first_reported_date': reference_date,
                                'last_reported_date': reference_date,
                            }
                        )
                        ccr_record.last_reported_date = reference_date

                        # Mark as closed if contract is settled
                        loan_is_settled = credit_info.get('is_settled', False) if is_month_3_test else getattr(
                            loanbook.loan, 'is_settled', False)

                        if loan_is_settled and not ccr_record.is_closed_in_ccr:
                            ccr_record.is_closed_in_ccr = True
                            if is_month_3_test:
                                ccr_record.closed_date = credit_info.get('contract_end_date', reference_date)
                            else:
                                ccr_record.closed_date = getattr(loanbook.loan, 'settled_date', reference_date)
                            print(f"Marked CCR record as closed for settled loanbook {loanbook.id}")

                        ccr_record.save()

                        # Create CCRContractSubmission tracking record
                        CCRContractSubmission.objects.create(
                            contract_record=ccr_record,
                            submission=submission,
                            submission_type=submission_type
                        )
                        print(f"Created {submission_type} contract submission tracking for loanbook {loanbook.id}")

            except Exception as e:
                print(f"Error processing CI record for loanbook {loanbook.id}: {e}")
                continue

        # --- FOOTER
        if submission_lines and len(submission_lines) > 1:
            footer = self.formatter.create_file_footer(len(submission_lines), reference_date)
            submission_lines.append(footer)
            print("Added footer")

        # Generate file content
        if not submission_lines:
            print("No data to report")
            file_content = ""
            total_records = 0
        else:
            file_content = '\n'.join(submission_lines)
            total_records = len(submission_lines)

        # Update submission record with final count
        if create_submission and submission:
            submission.total_records = total_records
            submission.save()
            print(f"Updated submission {submission.id} with {total_records} total records")

        # Create summary
        summary = {
            'reference_date': reference_date,
            'total_records': total_records,
            'new_contracts': len(new_loanbooks),
            'active_contracts': len(active_loanbooks) if not is_month_3_test else 0,
            'settled_contracts': len(settled_loanbooks),
            'is_test_mode': is_test_mode,
            'submission_id': submission.id if submission else None,
            'note': 'MONTH 3 SETTLEMENT SIMULATION' if is_month_3_test else 'Standard processing',
            'regenerated': is_regeneration
        }

        print(f"=== GENERATE_MONTHLY_SUBMISSION COMPLETE ===")
        print(f"Generated {total_records} records")
        if is_regeneration:
            print("*** FILE REGENERATED FROM EXISTING DATA ***")
        elif create_submission:
            # Count tracking records created
            tracking_count = CCRContractSubmission.objects.filter(submission=submission).count()
            print(f"*** CREATED {tracking_count} CONTRACT SUBMISSION TRACKING RECORDS ***")

        return file_content, total_records, summary

    def generate_file_content_only(self, reference_date, force_test_mode=False):
        """
        Generate file content without creating submission or updating database records
        Use this for regenerating files when submission already exists
        """
        print(f"=== GENERATE_FILE_CONTENT_ONLY ===")
        print(f"Reference date: {reference_date}")
        print(f"Force test mode: {force_test_mode}")

        return self.generate_monthly_submission(
            reference_date=reference_date,
            force_test_mode=force_test_mode,
            create_submission=False  # This prevents database changes and enables regeneration mode
        )

    def get_submission_preview(self, reference_date):
        """Get preview of what would be submitted without creating records"""
        return self.collector.get_submission_preview(reference_date)

    def get_submission_details(self, submission_id):
        """
        Get detailed breakdown of what was included in a specific submission
        Uses CCRContractSubmission records for precise tracking
        """
        try:
            submission = CCRSubmission.objects.get(id=submission_id)

            # Get all contract submissions for this submission
            contract_submissions = CCRContractSubmission.objects.filter(
                submission=submission
            ).select_related('contract_record__loanbook__loan__application')

            # Group by submission type
            breakdown = {
                'NEW': [],
                'UPDATE': [],
                'SETTLEMENT': []
            }

            for cs in contract_submissions:
                loanbook = cs.contract_record.loanbook
                applicant = loanbook.loan.application.applicants.first()

                contract_info = {
                    'loanbook_id': loanbook.id,
                    'loan_id': loanbook.loan.id,
                    'ccr_contract_id': cs.contract_record.ccr_contract_id,
                    'amount': float(loanbook.initial_amount),
                    'applicant_name': f"{applicant.first_name} {applicant.last_name}" if applicant else "Unknown",
                    'created_at': loanbook.created_at,
                    'first_reported': cs.contract_record.first_reported_date,
                    'submission_created_at': cs.created_at
                }

                breakdown[cs.submission_type].append(contract_info)

            return {
                'submission': {
                    'id': submission.id,
                    'reference_date': submission.reference_date,
                    'total_records': submission.total_records,
                    'is_test_submission': submission.is_test_submission,
                    'generated_at': submission.generated_at
                },
                'breakdown': breakdown,
                'summary': {
                    'new_contracts': len(breakdown['NEW']),
                    'updates': len(breakdown['UPDATE']),
                    'settlements': len(breakdown['SETTLEMENT']),
                    'total_contract_records': len(contract_submissions)
                }
            }

        except CCRSubmission.DoesNotExist:
            return {'error': 'Submission not found'}
        except Exception as e:
            return {'error': str(e)}
