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
        from_date = self.loan.paid_out_date or self.loan.approved_date
        principal = self.initial_amount  # Fixed: Use only initial_amount, not + fee_agreed
        transactions = self.loan.transactions.order_by('transaction_date')

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
            return statement

        # Calculate loan age in days
        loan_age_days = (on_date - from_date).days

        # Process transactions to get current principal
        current_principal = principal
        transaction_dates = {}

        for tx in transactions:
            tx_date = tx.transaction_date.date()
            if tx_date <= on_date:
                transaction_dates[tx_date] = tx.amount
                statement["transactions"].append({
                    "date": tx_date,
                    "amount": tx.amount,
                    "description": tx.description or ""
                })

        # Calculate interest day by day
        current_amount = current_principal

        # 1. YEARLY INTEREST - Applied immediately
        yearly_interest = current_principal * self.initial_fee_percentage / Decimal("100")
        statement["yearly_interest"] = yearly_interest

        # Base amount after yearly interest
        base_amount_after_yearly = current_principal + yearly_interest

        if loan_age_days <= 365:
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

            # Show payments if any
            running_total = base_amount_after_yearly
            for tx_date, payment_amount in transaction_dates.items():
                if tx_date <= on_date:
                    running_total -= payment_amount
                    current_principal -= payment_amount
                    days_from_start = (tx_date - from_date).days + 1

                    statement["daily_breakdown"].append({
                        "day": days_from_start,
                        "date": tx_date,
                        "type": "Payment",
                        "principal": current_principal,
                        "payment_amount": payment_amount,
                        "running_total": running_total,
                        "note": f"Payment of {payment_amount}"
                    })

        else:
            # After first year - show yearly interest, then compound daily interest from day 366+
            running_total = base_amount_after_yearly

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

            # Process payments within first year
            for tx_date, payment_amount in transaction_dates.items():
                if tx_date < from_date + timezone.timedelta(days=365):
                    running_total -= payment_amount
                    current_principal -= payment_amount
                    days_from_start = (tx_date - from_date).days + 1

                    statement["daily_breakdown"].append({
                        "day": days_from_start,
                        "date": tx_date,
                        "type": "Payment",
                        "principal": current_principal,
                        "payment_amount": payment_amount,
                        "running_total": running_total,
                        "note": f"Payment of {payment_amount}"
                    })

            # Days 366+: Compound daily interest
            daily_rate = Decimal("1") + (self.daily_fee_after_year_percentage / Decimal("100"))
            daily_interest_total = Decimal("0.00")

            for day in range(366, loan_age_days + 1):
                current_date = from_date + timezone.timedelta(days=day - 1)
                if current_date > on_date:
                    break

                # Check for transactions first
                if current_date in transaction_dates:
                    payment_amount = transaction_dates[current_date]
                    running_total -= payment_amount
                    current_principal -= payment_amount

                    statement["daily_breakdown"].append({
                        "day": day,
                        "date": current_date,
                        "type": "Payment",
                        "principal": current_principal,
                        "payment_amount": payment_amount,
                        "running_total": running_total,
                        "note": f"Payment of {payment_amount}"
                    })

                # Apply daily compound interest
                previous_total = running_total
                running_total = running_total * daily_rate
                daily_interest = running_total - previous_total
                daily_interest_total += daily_interest

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

            statement["daily_interest_total"] = daily_interest_total

        # Exit fee on statement date (percentage of current principal)
        exit_fee = current_principal * self.exit_fee_percentage / Decimal("100")
        statement["exit_fee"] = exit_fee

        # Add exit fee to final total
        final_total = running_total + exit_fee
        statement["total_due"] = final_total

        # Add exit fee to breakdown
        statement["daily_breakdown"].append({
            "day": loan_age_days + 1,
            "date": on_date,
            "type": "Exit Fee",
            "principal": current_principal,
            "interest_rate": f"{self.exit_fee_percentage}%",
            "interest_amount": exit_fee,
            "running_total": final_total,
            "note": f"Exit fee: {current_principal} × {self.exit_fee_percentage}%"
        })

        # Create segments for compatibility
        statement["segments"] = [{
            "start": from_date,
            "end": on_date,
            "principal": current_principal,
            "days": loan_age_days,
            "interest": statement["yearly_interest"] + statement["daily_interest_total"],
            "total": final_total
        }]

        # Summary
        statement["summary"] = {
            "loan_age_days": loan_age_days,
            "within_first_year": loan_age_days <= 365,
            "base_principal": current_principal,
            "yearly_interest": statement["yearly_interest"],
            "daily_interest_total": statement["daily_interest_total"],
            "exit_fee": exit_fee,
            "total_due": final_total
        }

        return statement

    def __str__(self):
        return f"LoanBook for Loan #{self.loan.id}"
