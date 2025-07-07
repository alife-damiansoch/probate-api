# ccr_reporting/services/data_collector.py - Fixed for regeneration
from datetime import timedelta
from decimal import Decimal
from django.conf import settings
import os


class CCRDataCollector:
    """Collect and format data for CCR submissions"""

    FIXED_LOAN_DAYS = 1095  # Fixed 3 years in days

    def debug_ccr_records(self, reference_date):
        """Debug method to see what CCR records exist"""
        print(f"=== DEBUG_CCR_RECORDS for {reference_date} ===")

        from ..models import CCRContractRecord

        # Get all CCR records
        all_records = CCRContractRecord.objects.all()
        print(f"Total CCR records in database: {all_records.count()}")

        for record in all_records:
            print(f"  Record ID: {record.id}")
            print(f"    LoanBook: {record.loanbook.id}")
            print(f"    Loan: {record.loanbook.loan.id}")
            print(f"    First reported: {record.first_reported_date}")
            print(f"    Last reported: {record.last_reported_date}")
            print(f"    Is closed in CCR: {record.is_closed_in_ccr}")
            print(f"    Loan is settled: {record.loanbook.loan.is_settled}")
            print(f"    Closed date: {record.closed_date}")
            print("    ---")

        # Now check what the filter should find
        start_of_current_month = reference_date.replace(day=1)
        print(f"Start of current month: {start_of_current_month}")

        # Check each condition separately
        print("=== CHECKING FILTER CONDITIONS ===")

        # Condition 1: Not closed in CCR
        not_closed = CCRContractRecord.objects.filter(is_closed_in_ccr=False)
        print(f"Records not closed in CCR: {not_closed.count()}")
        for record in not_closed:
            print(f"  - {record.loanbook.loan.id} (first: {record.first_reported_date})")

        # Condition 2: Loan not settled
        loan_not_settled = not_closed.filter(loanbook__loan__is_settled=False)
        print(f"Records with loan not settled: {loan_not_settled.count()}")
        for record in loan_not_settled:
            print(f"  - {record.loanbook.loan.id} (first: {record.first_reported_date})")

        # Condition 3: First reported before this month
        before_this_month = loan_not_settled.filter(first_reported_date__lt=start_of_current_month)
        print(f"Records first reported before this month: {before_this_month.count()}")
        for record in before_this_month:
            print(f"  - {record.loanbook.loan.id} (first: {record.first_reported_date})")

        print(f"=== DEBUG_CCR_RECORDS COMPLETE ===")
        return before_this_month

    def __init__(self):
        self.provider_code = getattr(settings, 'CCR_PROVIDER_CODE', 'ERR')

    def get_personal_info(self, applicant):
        """Extract personal information for CCR submission"""
        print(f"=== GET_PERSONAL_INFO ===")
        print(f"Processing applicant: {applicant}")

        # Check if it's a string or an object
        if isinstance(applicant, str):
            print(f"ERROR: Received string instead of applicant object: '{applicant}'")
            raise ValueError(f"Expected applicant object, got string: {applicant}")

        # Check if it has required attributes
        required_attrs = ['id', 'first_name', 'last_name']
        for attr in required_attrs:
            if not hasattr(applicant, attr):
                print(f"ERROR: Applicant missing required attribute: {attr}")
                raise ValueError(f"Applicant object missing required attribute: {attr}")

        personal_info = {
            'provider_code': self.provider_code,
            'provider_cis_no': f"CIS_{applicant.id}",
            'forename': applicant.first_name[:50],  # CCR field limits
            'surname': applicant.last_name[:50],
            'date_of_birth': applicant.date_of_birth,
            'address_line_1': applicant.address_line_1[:60] if applicant.address_line_1 else '',
            'address_line_2': applicant.address_line_2[:60] if applicant.address_line_2 else '',
            'city': applicant.city[:35] if applicant.city else '',
            'county': applicant.county[:35] if applicant.county else '',
            'postal_code': applicant.postal_code[:10] if applicant.postal_code else '',
            'country': applicant.country or 'Ireland',
            'ppsn': applicant.decrypted_pps if hasattr(applicant, 'decrypted_pps') else '',
            'email': applicant.email[:254] if applicant.email else '',
            'phone': applicant.phone_number[:17] if applicant.phone_number else '',
        }

        print(f"Personal info generated for: {personal_info['forename']} {personal_info['surname']}")
        print(f"=== GET_PERSONAL_INFO COMPLETE ===")
        return personal_info

    def get_credit_info(self, loanbook, reference_date):
        """Extract credit information for CCR submission with settlement handling"""
        print(f"=== GET_CREDIT_INFO ===")

        loan = loanbook.loan
        print(f"Getting credit info for loan {loan.id}")
        print(f"Loan is_settled: {loan.is_settled}")

        # Get applicant using the correct path
        try:
            applicant = loan.application.applicants.first()
            print(f"Got applicant: {applicant}")
            if applicant:
                print(f"Applicant ID: {applicant.id}")
            else:
                print("No applicant found!")
        except Exception as e:
            print(f"Error getting applicant: {e}")
            applicant = None

        # Calculate dates using FIXED 1095 days approach
        start_date = loanbook.created_at.date()
        maturity_date = start_date + timedelta(days=self.FIXED_LOAN_DAYS)

        print(f"Start date: {start_date}")
        print(f"Maturity date: {maturity_date}")

        # Determine contract phase and dates based on settlement status
        if loan.is_settled:
            print(f"Loan is settled on: {loan.settled_date}")
            # Check if closed at maturity or in advance
            if loan.settled_date and loan.settled_date >= maturity_date:
                contract_phase = 'Closed'  # Closed at maturity
                credit_status = 'Settlement'  # Changed: Use Settlement instead of Not Applicable
            else:
                contract_phase = 'Closed In Advance'  # Closed before maturity
                credit_status = 'Settlement'  # Indicate it was settled early

            contract_end_date = loan.settled_date
            next_payment_date = None  # No next payment for settled loans
            outstanding_payments_number = 0
            outstanding_balance = 0  # Settled loans have 0 balance
            next_payment_amount = 0
        else:
            contract_phase = 'Active'
            credit_status = 'Not Applicable'
            contract_end_date = None
            next_payment_date = maturity_date  # Single bullet payment
            outstanding_payments_number = 1
            # Calculate current outstanding balance
            outstanding_balance = loanbook.calculate_total_due(reference_date)
            next_payment_amount = loanbook.calculate_total_due(maturity_date)

        print(f"Contract phase: {contract_phase}")
        print(f"Credit status: {credit_status}")
        print(f"Outstanding balance: {outstanding_balance}")
        print(f"Contract end date: {contract_end_date}")

        credit_info = {
            'provider_code': self.provider_code,
            'provider_cis_no': f"CIS_{applicant.id}" if applicant else '',
            'provider_contract_no': str(loanbook.loan.id),
            'product_type': 'Premium Financing',
            'consumer_flag': True,
            'role_of_cis': 'Borrower',

            # Dates
            'start_date': start_date,
            'maturity_date': maturity_date,
            'contract_end_date': contract_end_date,  # Set for settled loans
            'next_payment_date': next_payment_date,

            # Amounts (in EUR)
            'financed_amount': loanbook.initial_amount,
            'outstanding_balance': outstanding_balance,
            'next_payment_amount': next_payment_amount,

            # Payment structure
            'total_planned_payments': 1,  # Single bullet payment
            'outstanding_payments_number': outstanding_payments_number,
            'payment_frequency': 'Bullet',

            # Status
            'contract_phase': contract_phase,  # 'Active', 'Closed', or 'Closed In Advance'
            'credit_status': credit_status,  # 'Not Applicable' or 'Settlement'
            'is_settled': loan.is_settled,

            # Currency
            'currency': 'EUR',
            'original_currency': 'EUR',

            # Additional fields
            'interest_rate_type': 'Other Interest Rate Type',
            'purpose_of_credit_type': 'Other purposes',
        }

        print(
            f"Credit info generated: contract_no={credit_info['provider_contract_no']}, phase={credit_info['contract_phase']}")
        print(f"=== GET_CREDIT_INFO COMPLETE ===")

        return credit_info

    def get_new_loanbooks(self, reference_date, ignore_already_reported=False):
        """Get LoanBooks created in the reference month that haven't been reported

        Args:
            reference_date: The reference date for the submission
            ignore_already_reported: If True, include loanbooks that already have CCR records
                                   (useful for regeneration)
        """
        print(f"=== GET_NEW_LOANBOOKS ===")
        print(f"Reference date: {reference_date}")
        print(f"Ignore already reported: {ignore_already_reported}")

        from loanbook.models import LoanBook
        from ..models import CCRContractRecord

        # Get loanbooks created in reference month
        start_of_month = reference_date.replace(day=1)
        print(f"Start of month: {start_of_month}")

        print("Step 1: Filtering by date range...")
        date_filtered = LoanBook.objects.filter(
            created_at__date__gte=start_of_month,
            created_at__date__lte=reference_date
        )
        print(f"  Found {date_filtered.count()} loanbooks in date range")

        print("Step 2: Filtering by amount >= €500...")
        amount_filtered = date_filtered.filter(initial_amount__gte=Decimal('500.00'))
        print(f"  Found {amount_filtered.count()} loanbooks with amount >= €500")

        if ignore_already_reported:
            print("Step 3: Including all loanbooks (ignoring already reported status)...")
            new_loanbooks = amount_filtered
            print(f"  Found {new_loanbooks.count()} loanbooks (including already reported)")
        else:
            print("Step 3: Excluding already reported...")
            new_loanbooks = amount_filtered.exclude(ccr_record__isnull=False)
            print(f"  Found {new_loanbooks.count()} new loanbooks (not yet reported)")

        for lb in new_loanbooks:
            has_ccr_record = hasattr(lb, 'ccr_record') and lb.ccr_record is not None
            print(
                f"    - LoanBook {lb.id} (Loan #{lb.loan.id}), Amount: €{lb.initial_amount}, Created: {lb.created_at}, Has CCR Record: {has_ccr_record}")

        print(f"=== GET_NEW_LOANBOOKS COMPLETE: {new_loanbooks.count()} found ===")
        return new_loanbooks

    def get_active_loanbooks(self, reference_date, for_regeneration=False):
        """Get LoanBooks that need monthly updates (active, not settled)"""
        print(f"=== GET_ACTIVE_LOANBOOKS ===")
        print(f"Reference date: {reference_date}")
        print(f"For regeneration: {for_regeneration}")

        from ..models import CCRContractRecord

        # Add debugging
        self.debug_ccr_records(reference_date)

        if for_regeneration:
            # For regeneration: get all CCR records that were updated on this date
            # and were active (not closed) at that time
            active_records = CCRContractRecord.objects.filter(
                last_reported_date=reference_date,
                first_reported_date__lt=reference_date,  # Was reported before this month
            ).exclude(
                closed_date=reference_date  # Exclude ones that were closed on this date
            )
        else:
            # Normal mode: get currently active loans that have been reported before
            # Calculate start of current month to check if contract was reported before this month
            start_of_current_month = reference_date.replace(day=1)
            print(f"Looking for contracts first reported before: {start_of_current_month}")

            active_records = CCRContractRecord.objects.filter(
                is_closed_in_ccr=False,  # Not closed in CCR
                loanbook__loan__is_settled=False,  # Loan is not settled
                first_reported_date__lt=start_of_current_month  # Was first reported before this month
            )

            print(f"Query found {active_records.count()} active records")

        active_loanbooks = [record.loanbook for record in active_records]
        print(f"Found {len(active_loanbooks)} active loanbooks for monthly update")

        for lb in active_loanbooks:
            if hasattr(lb, 'ccr_record'):
                first_reported = lb.ccr_record.first_reported_date
                last_reported = lb.ccr_record.last_reported_date
                print(
                    f"  - LoanBook {lb.id} (Loan #{lb.loan.id}), Amount: €{lb.initial_amount}, First: {first_reported}, Last: {last_reported}")
            else:
                print(f"  - LoanBook {lb.id} (Loan #{lb.loan.id}), Amount: €{lb.initial_amount}, No CCR record")

        print(f"=== GET_ACTIVE_LOANBOOKS COMPLETE: {len(active_loanbooks)} found ===")
        return active_loanbooks

    def get_settled_loanbooks(self, reference_date, for_regeneration=False):
        """Get LoanBooks settled in reference month that need final reporting

        Args:
            reference_date: The reference date for the submission
            for_regeneration: If True, get loanbooks that were settled at this date
                            (useful for regeneration)
        """
        print(f"=== GET_SETTLED_LOANBOOKS ===")
        print(f"Reference date: {reference_date}")
        print(f"For regeneration: {for_regeneration}")

        from loanbook.models import LoanBook
        from ..models import CCRContractRecord

        start_of_month = reference_date.replace(day=1)
        print(f"Start of month: {start_of_month}")

        if for_regeneration:
            # For regeneration: get CCR records that were closed on this date
            settled_records = CCRContractRecord.objects.filter(
                closed_date=reference_date,
                is_closed_in_ccr=True
            )
        else:
            # Normal mode: get loans settled this month that need reporting
            settled_records = CCRContractRecord.objects.filter(
                is_closed_in_ccr=False,  # Not yet closed in CCR
                loanbook__loan__is_settled=True,  # Loan is settled
                loanbook__loan__settled_date__gte=start_of_month,  # Settled this month
                loanbook__loan__settled_date__lte=reference_date
            )

        settled_loanbooks = [record.loanbook for record in settled_records]
        print(f"Found {len(settled_loanbooks)} settled loanbooks for final reporting")

        for lb in settled_loanbooks:
            settled_date = getattr(lb.loan, 'settled_date', 'Unknown')
            print(f"  - LoanBook {lb.id} (Loan #{lb.loan.id}), Settled: {settled_date}")

        print(f"=== GET_SETTLED_LOANBOOKS COMPLETE: {len(settled_loanbooks)} found ===")
        return settled_loanbooks

    def get_submission_preview(self, reference_date):
        """Get preview data for potential submission without generating file"""
        print(f"=== GET_SUBMISSION_PREVIEW ===")
        print(f"Reference date: {reference_date}")

        # Get all the different types of loanbooks
        new_loanbooks = self.get_new_loanbooks(reference_date)
        active_loanbooks = self.get_active_loanbooks(reference_date)
        settled_loanbooks = self.get_settled_loanbooks(reference_date)

        # Count records that would be generated
        header_count = 1 if (new_loanbooks or active_loanbooks or settled_loanbooks) else 0
        footer_count = 1 if (new_loanbooks or active_loanbooks or settled_loanbooks) else 0

        # ID records for new applicants
        id_record_count = 0
        if new_loanbooks:
            # Check which applicants haven't been reported before
            for loanbook in new_loanbooks:
                try:
                    applicant = loanbook.loan.application.applicants.first()
                    if applicant and not getattr(applicant, 'ccr_reported', False):
                        id_record_count += 1
                except Exception:
                    continue

        # CI records for all contracts
        ci_record_count = len(active_loanbooks) + len(settled_loanbooks)
        # Note: new_loanbooks only get ID records, CI records come next month

        total_records = header_count + id_record_count + ci_record_count + footer_count

        preview_data = {
            'reference_date': reference_date,
            'total_records': total_records,
            'new_contracts': {
                'count': len(new_loanbooks),
                'details': [
                    {
                        'loanbook_id': lb.id,
                        'loan_id': lb.loan.id,
                        'amount': float(lb.initial_amount),
                        'created_at': lb.created_at,
                        'applicant_name': f"{lb.loan.application.applicants.first().first_name} {lb.loan.application.applicants.first().last_name}" if lb.loan.application.applicants.first() else "Unknown"
                    } for lb in new_loanbooks[:10]  # Limit to first 10 for preview
                ]
            },
            'active_contracts': {
                'count': len(active_loanbooks),
                'details': [
                    {
                        'loanbook_id': lb.id,
                        'loan_id': lb.loan.id,
                        'amount': float(lb.initial_amount),
                        'first_reported': lb.ccr_record.first_reported_date if hasattr(lb, 'ccr_record') else None,
                        'applicant_name': f"{lb.loan.application.applicants.first().first_name} {lb.loan.application.applicants.first().last_name}" if lb.loan.application.applicants.first() else "Unknown"
                    } for lb in active_loanbooks[:10]  # Limit to first 10 for preview
                ]
            },
            'settled_contracts': {
                'count': len(settled_loanbooks),
                'details': [
                    {
                        'loanbook_id': lb.id,
                        'loan_id': lb.loan.id,
                        'amount': float(lb.initial_amount),
                        'settled_date': lb.loan.settled_date,
                        'applicant_name': f"{lb.loan.application.applicants.first().first_name} {lb.loan.application.applicants.first().last_name}" if lb.loan.application.applicants.first() else "Unknown"
                    } for lb in settled_loanbooks[:10]  # Limit to first 10 for preview
                ]
            },
            'breakdown': {
                'header_records': header_count,
                'id_records': id_record_count,
                'ci_records': ci_record_count,
                'footer_records': footer_count,
            }
        }

        print(f"=== GET_SUBMISSION_PREVIEW COMPLETE ===")
        return preview_data
