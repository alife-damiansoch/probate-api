from django.db import models
from django.utils import timezone
from decimal import Decimal
from core.models import Loan  # or from loans.models import Loan depending on your project structure


class LoanBook(models.Model):
    loan = models.OneToOneField(Loan, on_delete=models.CASCADE, primary_key=True, related_name='loanbook')

    initial_amount = models.DecimalField(max_digits=14, decimal_places=2,
                                         help_text="Snapshot of loan.amount_agreed at time of creation")
    estate_net_value = models.DecimalField(max_digits=14, decimal_places=2)

    # Admin-editable fees
    initial_fee_percentage = models.DecimalField(default=Decimal("15.00"), max_digits=5, decimal_places=2)
    daily_fee_after_year_percentage = models.DecimalField(default=Decimal("0.07"), max_digits=5, decimal_places=2)
    exit_fee_percentage = models.DecimalField(default=Decimal("1.50"), max_digits=5, decimal_places=2)

    created_at = models.DateTimeField(null=True, blank=True)

    def calculate_total_due(self, on_date=None):
        statement = self.generate_statement(on_date)
        return statement["total_due"]

    def generate_statement(self, on_date=None):
        on_date = on_date or timezone.now().date()
        print(f"=== STATEMENT GENERATION STARTING ===")
        print(f"Statement date: {on_date}")
        print(f"Current timezone: {timezone.now()}")
        print(f"Current date: {timezone.now().date()}")

        # CHECK FOR SETTLEMENT FIRST
        if self.loan.is_settled and self.loan.settled_date:
            settled_date = self.loan.settled_date.date() if hasattr(self.loan.settled_date,
                                                                    'date') else self.loan.settled_date
            print(f"=== LOAN IS SETTLED ===")
            print(f"Settled date: {settled_date}")

            # If statement date is after settlement, use settlement date instead
            if on_date > settled_date:
                print(f"Statement date {on_date} is after settlement date {settled_date}")
                print(f"Generating statement only until settlement date: {settled_date}")
                on_date = settled_date
            else:
                print(f"Statement date {on_date} is on or before settlement date {settled_date}")

        from_date = self.loan.paid_out_date or self.loan.approved_date
        print(f"From date (loan start): {from_date}")

        principal = self.initial_amount  # Fixed: Use only initial_amount, not + fee_agreed
        print(f"Initial principal: {principal}")

        transactions = self.loan.transactions.order_by('transaction_date')
        print(f"Total transactions in queryset: {transactions.count()}")

        statement = {
            "date": on_date,
            "initial_amount": self.initial_amount,
            "yearly_interest": Decimal("0.00"),
            "daily_interest_total": Decimal("0.00"),
            "exit_fee": Decimal("0.00"),
            "daily_breakdown": [],  # Day by day breakdown
            "segments": [],
            "transactions": [],
            "total_due": Decimal("0.00")
        }

        if not from_date:
            print("ERROR: No from_date found!")
            return statement

        # Calculate loan age in days (inclusive of statement date)
        loan_age_days = (on_date - from_date).days + 1
        print(f"Loan age in days (inclusive): {loan_age_days}")
        print(f"This means we process from day 1 through day {loan_age_days}")

        # Process transactions to get current principal
        current_principal = principal
        transaction_dates = {}  # Will store lists of transactions per date

        print(f"\n=== PROCESSING TRANSACTIONS ===")
        # FIXED: Handle multiple transactions per day separately
        for tx in transactions:
            tx_date = tx.transaction_date.date()
            print(f"Transaction: {tx.transaction_date} -> Date: {tx_date}, Amount: {tx.amount}")
            print(f"Comparison: {tx_date} <= {on_date} = {tx_date <= on_date}")
            if tx_date <= on_date:
                print(f"  ✓ INCLUDED in calculation")
                # Store as list to handle multiple transactions per day
                if tx_date not in transaction_dates:
                    transaction_dates[tx_date] = []
                transaction_dates[tx_date].append({
                    'amount': tx.amount,
                    'description': tx.description or ""
                })

                statement["transactions"].append({
                    "date": tx_date,
                    "amount": tx.amount,
                    "description": tx.description or ""
                })
            else:
                print(f"  ✗ EXCLUDED from calculation (after statement date)")

        print(f"\n=== TRANSACTION SUMMARY ===")
        print(f"Total transactions found: {len(transactions)}")
        print(f"Transaction dates dictionary: {transaction_dates}")
        print(f"Statement transactions count: {len(statement['transactions'])}")

        # Calculate interest day by day
        current_amount = current_principal

        # 1. YEARLY INTEREST - Applied immediately
        yearly_interest = current_principal * self.initial_fee_percentage / Decimal("100")
        statement["yearly_interest"] = yearly_interest
        print(f"\nYearly interest calculated: {yearly_interest}")

        # Base amount after yearly interest
        base_amount_after_yearly = current_principal + yearly_interest
        print(f"Base amount after yearly interest: {base_amount_after_yearly}")

        if loan_age_days <= 366:  # Changed from 365 to 366 to include day 366
            print(f"\n=== FIRST YEAR PROCESSING (loan_age_days = {loan_age_days}) ===")
            # Within first year - only show key entries
            statement["daily_breakdown"].append({
                "day": 1,
                "date": from_date,
                "type": "Yearly Interest Applied",
                "principal": current_principal,
                "interest_rate": f"{self.initial_fee_percentage}%",
                "interest_amount": yearly_interest,
                "running_total": base_amount_after_yearly,
                "note": f"Flat {self.initial_fee_percentage}% yearly interest"
            })

            # FIXED: Process each transaction separately within first year
            running_total = base_amount_after_yearly
            print(f"Starting running_total: {running_total}")
            print(f"Starting current_principal: {current_principal}")

            for tx_date, transactions_list in transaction_dates.items():
                print(f"\nChecking date {tx_date} <= {on_date}: {tx_date <= on_date}")
                if tx_date <= on_date:
                    print(f"Processing {len(transactions_list)} transactions on {tx_date}")
                    for i, tx_data in enumerate(transactions_list):
                        payment_amount = tx_data['amount']
                        print(f"  Transaction {i + 1}:")
                        print(f"    BEFORE: running_total={running_total}, principal={current_principal}")

                        running_total -= payment_amount
                        current_principal -= payment_amount
                        days_from_start = (tx_date - from_date).days + 1

                        print(
                            f"    AFTER payment of {payment_amount}: running_total={running_total}, principal={current_principal}")

                        statement["daily_breakdown"].append({
                            "day": days_from_start,
                            "date": tx_date,
                            "type": "Payment",
                            "principal": current_principal,
                            "payment_amount": payment_amount,
                            "running_total": running_total,
                            "note": f"Payment of {payment_amount} - {tx_data['description']}"
                        })
                        print(f"    Added to daily_breakdown: Payment of {payment_amount}")
                else:
                    print(f"Skipping date {tx_date} (after statement date)")

            print(f"\nFinal running_total after payments: {running_total}")
            print(f"Final current_principal after payments: {current_principal}")

        else:
            print(f"\n=== AFTER FIRST YEAR PROCESSING (loan_age_days = {loan_age_days}) ===")
            # After first year - show yearly interest, then compound daily interest from day 366+
            running_total = base_amount_after_yearly
            print(f"Starting running_total: {running_total}")
            print(f"Starting current_principal: {current_principal}")

            # Show yearly interest application
            statement["daily_breakdown"].append({
                "day": 1,
                "date": from_date,
                "type": "Yearly Interest Applied",
                "principal": current_principal,
                "interest_rate": f"{self.initial_fee_percentage}%",
                "interest_amount": yearly_interest,
                "running_total": running_total,
                "note": f"Flat {self.initial_fee_percentage}% yearly interest"
            })

            # FIXED: Process payments within first year (each transaction separately)
            print(f"\n--- Processing payments within first year ---")
            for tx_date, transactions_list in transaction_dates.items():
                first_year_cutoff = from_date + timezone.timedelta(days=366)  # Changed from 365 to 366
                print(f"Checking date {tx_date} < {first_year_cutoff}: {tx_date < first_year_cutoff}")
                if tx_date < first_year_cutoff:
                    print(f"Processing {len(transactions_list)} transactions on {tx_date} (within first year)")
                    for i, tx_data in enumerate(transactions_list):
                        payment_amount = tx_data['amount']
                        print(f"  Transaction {i + 1}:")
                        print(f"    BEFORE: running_total={running_total}, principal={current_principal}")

                        running_total -= payment_amount
                        current_principal -= payment_amount
                        days_from_start = (tx_date - from_date).days + 1

                        print(
                            f"    AFTER payment of {payment_amount}: running_total={running_total}, principal={current_principal}")

                        statement["daily_breakdown"].append({
                            "day": days_from_start,
                            "date": tx_date,
                            "type": "Payment",
                            "principal": current_principal,
                            "payment_amount": payment_amount,
                            "running_total": running_total,
                            "note": f"Payment of {payment_amount} - {tx_data['description']}"
                        })
                        print(f"    Added to daily_breakdown: Payment of {payment_amount}")
                else:
                    print(f"Transaction on {tx_date} is after first year, will be processed in daily loop")

            # Days 367+: Compound daily interest (changed from 366+ to 367+)
            print(f"\n--- Processing days 367+ with compound interest ---")
            daily_rate = Decimal("1") + (self.daily_fee_after_year_percentage / Decimal("100"))
            daily_interest_total = Decimal("0.00")
            print(f"Daily rate: {daily_rate}")

            for day in range(367, loan_age_days + 1):  # Changed from 366 to 367
                current_date = from_date + timezone.timedelta(days=day - 1)
                if current_date > on_date:
                    print(f"Day {day} ({current_date}) is after statement date, breaking")
                    break

                print(f"\nDay {day} ({current_date}):")

                # FIRST: Apply daily compound interest (on amount at START of day)
                previous_total = running_total
                running_total = running_total * daily_rate
                daily_interest = running_total - previous_total
                daily_interest_total += daily_interest

                print(
                    f"  Interest FIRST: {previous_total} × {daily_rate} = {running_total} (interest: {daily_interest})")

                statement["daily_breakdown"].append({
                    "day": day,
                    "date": current_date,
                    "type": "Daily Compound Interest",
                    "principal": current_principal,
                    "interest_rate": f"{self.daily_fee_after_year_percentage}%",
                    "interest_amount": daily_interest,
                    "running_total": running_total,
                    "note": f"Compound interest: {previous_total} × {daily_rate}"
                })

                # THEN: Process payments (reducing amounts for next day)
                if current_date in transaction_dates:
                    print(f"  Found {len(transaction_dates[current_date])} transactions on this day")
                    for i, tx_data in enumerate(transaction_dates[current_date]):
                        payment_amount = tx_data['amount']
                        print(
                            f"    Transaction {i + 1}: BEFORE payment - running_total={running_total}, principal={current_principal}")

                        running_total -= payment_amount
                        current_principal -= payment_amount

                        print(
                            f"    Transaction {i + 1}: AFTER payment of {payment_amount} - running_total={running_total}, principal={current_principal}")

                        statement["daily_breakdown"].append({
                            "day": day,
                            "date": current_date,
                            "type": "Payment",
                            "principal": current_principal,
                            "payment_amount": payment_amount,
                            "running_total": running_total,
                            "note": f"Payment of {payment_amount} - {tx_data['description']}"
                        })
                else:
                    print(f"  No transactions on this day")

            statement["daily_interest_total"] = daily_interest_total
            print(f"\nTotal daily interest: {daily_interest_total}")

        # Exit fee on statement date (percentage of current principal BEFORE any payments today)
        # We need to calculate what the principal was at START of statement day
        principal_start_of_day = current_principal

        # If there are payments today, add them back to get start-of-day principal
        if on_date in transaction_dates:
            for tx_data in transaction_dates[on_date]:
                principal_start_of_day += tx_data['amount']

        exit_fee = principal_start_of_day * self.exit_fee_percentage / Decimal("100")
        statement["exit_fee"] = exit_fee
        print(f"\n=== EXIT FEE CALCULATION ===")
        print(f"Principal at start of day: {principal_start_of_day}")
        print(f"Exit fee: {principal_start_of_day} × {self.exit_fee_percentage}% = {exit_fee}")
        print(f"Current principal after payments: {current_principal}")

        # Add exit fee to final total
        final_total = running_total + exit_fee
        statement["total_due"] = final_total
        print(f"Final total: {running_total} + {exit_fee} = {final_total}")

        # Add exit fee to breakdown
        statement["daily_breakdown"].append({
            "day": loan_age_days,  # Changed: Use current loan_age_days instead of +1
            "date": on_date,
            "type": "Exit Fee",
            "principal": principal_start_of_day,  # Show the principal it was calculated on
            "interest_rate": f"{self.exit_fee_percentage}%",
            "interest_amount": exit_fee,
            "running_total": final_total,
            "note": f"Exit fee: {principal_start_of_day} × {self.exit_fee_percentage}% (calculated on start-of-day principal)"
        })

        # Create segments for compatibility
        total_interest_earned = statement["yearly_interest"] + statement["daily_interest_total"]
        total_payments_made = sum(tx['amount'] for tx in statement["transactions"])

        # The segment total should represent: Total Payments Made + Amount Still Due
        segment_total = total_payments_made + final_total

        # Create segments with full breakdown
        total_payments_made = sum(tx['amount'] for tx in statement["transactions"])
        segment_total = total_payments_made + final_total

        statement["segments"] = [{
            "start": from_date,
            "end": on_date,
            "principal": self.initial_amount,
            "first_year_interest": statement["yearly_interest"],  # 15% flat interest
            "daily_interest_accumulated": statement["daily_interest_total"],  # 0.07% compound daily after year 1
            "exit_fee": statement["exit_fee"],
            "total_interest": statement["yearly_interest"] + statement["daily_interest_total"],  # Sum of above three
            "total_payments_made": total_payments_made,
            "total": segment_total  # Total loan obligation
        }]
        # Summary
        statement["summary"] = {
            "loan_age_days": loan_age_days,
            "within_first_year": loan_age_days <= 366,  # Updated to match the logic above
            "base_principal": current_principal,
            "yearly_interest": statement["yearly_interest"],
            "daily_interest_total": statement["daily_interest_total"],
            "exit_fee": exit_fee,
            "total_due": final_total
        }

        print(f"\n=== FINAL STATEMENT SUMMARY ===")
        print(f"Daily breakdown entries: {len(statement['daily_breakdown'])}")
        print(f"Total transactions in statement: {len(statement['transactions'])}")
        print(f"Total due: {statement['total_due']}")

        # Add settlement info to statement if loan is settled
        if self.loan.is_settled and self.loan.settled_date:
            settled_date = self.loan.settled_date.date() if hasattr(self.loan.settled_date,
                                                                    'date') else self.loan.settled_date
            statement["is_settled"] = True
            statement["settled_date"] = settled_date
            print(f"LOAN STATUS: SETTLED on {settled_date}")

            # Add settlement entry to daily breakdown
            statement["daily_breakdown"].append({
                "day": "FINAL",
                "date": settled_date,
                "type": "LOAN SETTLED",
                "principal": Decimal("0.00"),
                "interest_rate": "N/A",
                "interest_amount": Decimal("0.00"),
                "running_total": Decimal("0.00"),
                "note": f"LOAN SETTLED ON {settled_date}"
            })
        else:
            statement["is_settled"] = False
            statement["settled_date"] = None
            print(f"LOAN STATUS: ACTIVE")

        print(f"=== STATEMENT GENERATION COMPLETE ===\n")

        return statement

    def __str__(self):
        return f"LoanBook for Loan #{self.loan.id}"
