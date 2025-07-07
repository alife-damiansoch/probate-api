# debug_ccr.py
from datetime import datetime, date
from decimal import Decimal
from ccr_reporting.services.data_collector import CCRDataCollector
from loanbook.models import LoanBook


def debug_ccr():
    reference_date = date(2025, 7, 31)
    print(f"Testing CCR for date: {reference_date}")

    # Your specific loanbooks
    july_3_loanbooks = LoanBook.objects.filter(created_at__date=date(2025, 7, 3))
    print(f"\nLoanbooks created on July 3rd: {july_3_loanbooks.count()}")

    for lb in july_3_loanbooks:
        print(f"\nLoanBook {lb.id} (Loan #{lb.loan.id}):")
        print(f"  Created: {lb.created_at}")
        print(f"  Amount: €{lb.initial_amount}")

        # Check all the conditions
        amount_ok = lb.initial_amount >= Decimal('500.00')
        print(f"  Amount >= €500: {amount_ok}")

        # Date range check
        start_of_month = reference_date.replace(day=1)
        date_ok = (lb.created_at.date() >= start_of_month and
                   lb.created_at.date() <= reference_date)
        print(f"  In date range: {date_ok}")

        # CCR record check
        try:
            ccr_record = lb.ccr_record
            print(f"  Has CCR record: YES (ID: {ccr_record.id})")
            has_ccr = True
        except:
            print(f"  Has CCR record: NO")
            has_ccr = False

        # Applicant check
        try:
            applicant = lb.loan.first_applicant()
            print(f"  Has applicant: {applicant is not None}")
        except Exception as e:
            print(f"  Applicant error: {e}")

        # Final verdict
        should_be_included = amount_ok and date_ok and not has_ccr
        print(f"  Should be included: {should_be_included}")

    # Test CCR collector
    print(f"\n--- CCR Collector Results ---")
    collector = CCRDataCollector()
    new_loanbooks = collector.get_new_loanbooks(reference_date)
    print(f"Found {new_loanbooks.count()} new loanbooks")

    for lb in new_loanbooks:
        print(f"  - LoanBook {lb.id} (Loan #{lb.loan.id})")


# Run the debug
debug_ccr()
