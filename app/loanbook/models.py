import os
from django.db import models
from django.utils import timezone
from decimal import Decimal
from core.models import Loan  # or from loans.models import Loan depending on your project structure

# FIXED: Use constant 365-day year throughout
DAYS_IN_YEAR = 365


def get_initial_fee_default():
    value = os.getenv('INITIAL_FEE_PERCENTAGE')
    if value is None:
        raise ValueError("INITIAL_FEE_PERCENTAGE environment variable is required but not set")
    return Decimal(value)


def get_daily_fee_default():
    value = os.getenv('DAILY_FEE_AFTER_YEAR_PERCENTAGE')
    if value is None:
        raise ValueError("DAILY_FEE_AFTER_YEAR_PERCENTAGE environment variable is required but not set")
    return Decimal(value)


def get_exit_fee_default():
    value = os.getenv('EXIT_FEE_PERCENTAGE')
    if value is None:
        raise ValueError("EXIT_FEE_PERCENTAGE environment variable is required but not set")
    return Decimal(value)


class LoanBook(models.Model):
    loan = models.OneToOneField(Loan, on_delete=models.CASCADE, primary_key=True, related_name='loanbook')

    initial_amount = models.DecimalField(max_digits=14, decimal_places=2,
                                         help_text="Snapshot of loan.amount_agreed at time of creation")
    estate_net_value = models.DecimalField(max_digits=14, decimal_places=2)

    initial_fee_percentage = models.DecimalField(max_digits=5, decimal_places=2,
                                                 default=get_initial_fee_default,
                                                 help_text="First year flat fee percentage")
    daily_fee_after_year_percentage = models.DecimalField(max_digits=5, decimal_places=2,
                                                          default=get_daily_fee_default,
                                                          help_text="Daily fee percentage after first year")
    exit_fee_percentage = models.DecimalField(max_digits=5, decimal_places=2,
                                              default=get_exit_fee_default,
                                              help_text="Exit fee percentage on settlement")

    created_at = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.pk:
            if self.created_at and hasattr(self.created_at, 'date'):
                pass
            elif self.created_at:
                self.created_at = timezone.make_aware(
                    timezone.datetime.combine(self.created_at, timezone.time.min)
                )
            else:
                self.created_at = timezone.now()

        super().save(*args, **kwargs)

    @classmethod
    def create_with_custom_fees(cls, loan, initial_amount, estate_net_value,
                                initial_fee_percentage=None,
                                daily_fee_after_year_percentage=None,
                                exit_fee_percentage=None):
        loanbook = cls(
            loan=loan,
            initial_amount=initial_amount,
            estate_net_value=estate_net_value,
            created_at=timezone.now()
        )
        if initial_fee_percentage is not None:
            loanbook.initial_fee_percentage = Decimal(str(initial_fee_percentage))
            loanbook._initial_fee_percentage_set = True

        if daily_fee_after_year_percentage is not None:
            loanbook.daily_fee_after_year_percentage = Decimal(str(daily_fee_after_year_percentage))
            loanbook._daily_fee_after_year_percentage_set = True

        if exit_fee_percentage is not None:
            loanbook.exit_fee_percentage = Decimal(str(exit_fee_percentage))
            loanbook._exit_fee_percentage_set = True

        loanbook.save()
        return loanbook

    @classmethod
    def get_default_fees_from_env(cls):
        return {
            'initial_fee_percentage': get_initial_fee_default(),
            'daily_fee_after_year_percentage': get_daily_fee_default(),
            'exit_fee_percentage': get_exit_fee_default()
        }

    @staticmethod
    def calculate_probate_costs(initial_amount, initial_fee_percentage, daily_fee_percentage, exit_fee_percentage,
                                months):
        """
        Calculate probate advancement costs using FIXED 365-day year

        Args:
            initial_amount: Principal amount (Decimal)
            initial_fee_percentage: First year fee % (Decimal)
            daily_fee_percentage: Daily fee % after first year (Decimal)
            exit_fee_percentage: Exit fee % (Decimal)
            months: Number of months to calculate for (int)

        Returns:
            dict with all cost calculations (rounded to 2 decimal places)
        """
        initial_amount = Decimal(str(initial_amount))
        initial_fee_percentage = Decimal(str(initial_fee_percentage))
        daily_fee_percentage = Decimal(str(daily_fee_percentage))
        exit_fee_percentage = Decimal(str(exit_fee_percentage))

        # First year charge (applied immediately)
        first_year_charge = initial_amount * (initial_fee_percentage / Decimal("100"))
        running_total = initial_amount + first_year_charge

        # Daily interest calculation (only if more than 12 months)
        daily_interest_total = Decimal("0.00")
        if months > 12:
            # FIXED: Use exactly 365 days per 12 months, not calendar months
            # This ensures consistency: 36 months = exactly 1095 days total
            days_after_first_year = int((months - 12) * DAYS_IN_YEAR / 12)

            # Apply simple daily interest: principal × daily_rate × days
            daily_interest_per_day = initial_amount * (daily_fee_percentage / Decimal("100"))
            daily_interest_total = daily_interest_per_day * days_after_first_year
            running_total += daily_interest_total

        # Exit fee on remaining principal
        exit_fee = initial_amount * (exit_fee_percentage / Decimal("100"))

        # Total amount payable
        total_payable = running_total + exit_fee
        total_cost = first_year_charge + daily_interest_total + exit_fee

        return {
            'initial_amount': initial_amount.quantize(Decimal('0.01')),
            'first_year_charge': first_year_charge.quantize(Decimal('0.01')),
            'daily_interest_total': daily_interest_total.quantize(Decimal('0.01')),
            'exit_fee': exit_fee.quantize(Decimal('0.01')),
            'total_cost': total_cost.quantize(Decimal('0.01')),
            'total_payable': total_payable.quantize(Decimal('0.01')),
            'months': months,
            'days_after_first_year': int((months - 12) * DAYS_IN_YEAR / 12) if months > 12 else 0
        }

    @classmethod
    def calculate_secci_scenarios(cls, initial_amount, initial_fee_percentage=None, daily_fee_percentage=None,
                                  exit_fee_percentage=None):
        """
        Calculate minimum (12 months) and maximum (36 months) scenarios for SECCI
        Uses environment variables if percentages not provided
        """
        if initial_fee_percentage is None:
            initial_fee_percentage = Decimal(os.getenv('INITIAL_FEE_PERCENTAGE', '15.00'))
        if daily_fee_percentage is None:
            daily_fee_percentage = Decimal(os.getenv('DAILY_FEE_AFTER_YEAR_PERCENTAGE', '0.07'))
        if exit_fee_percentage is None:
            exit_fee_percentage = Decimal(os.getenv('EXIT_FEE_PERCENTAGE', '1.50'))

        # Calculate minimum scenario (12 months)
        min_scenario = cls.calculate_probate_costs(
            initial_amount, initial_fee_percentage, daily_fee_percentage, exit_fee_percentage, 12
        )

        # Calculate maximum scenario (36 months)
        max_scenario = cls.calculate_probate_costs(
            initial_amount, initial_fee_percentage, daily_fee_percentage, exit_fee_percentage, 36
        )

        return {
            'minimum': min_scenario,
            'maximum': max_scenario,
            'fee_percentages': {
                'initial_fee_percentage': initial_fee_percentage,
                'daily_fee_percentage': daily_fee_percentage,
                'exit_fee_percentage': exit_fee_percentage
            }
        }

    def calculate_total_due(self, on_date=None):
        """Updated to use the static calculation method when possible"""
        statement = self.generate_statement(on_date)
        return statement["total_due"]

    def generate_statement(self, on_date=None):
        """
        Generate statement using FIXED 365-day year calculations
        """
        on_date = on_date or timezone.now().date()

        # CHECK FOR SETTLEMENT FIRST
        if self.loan.is_settled and self.loan.settled_date:
            settled_date = self.loan.settled_date.date() if hasattr(self.loan.settled_date,
                                                                    'date') else self.loan.settled_date
            if on_date > settled_date:
                on_date = settled_date

        from_date = self.loan.paid_out_date or self.loan.approved_date
        principal = self.initial_amount
        transactions = self.loan.transactions.order_by('transaction_date')

        statement = {
            "date": on_date,
            "initial_amount": self.initial_amount,
            "yearly_interest": Decimal("0.00"),
            "daily_interest_total": Decimal("0.00"),
            "exit_fee": Decimal("0.00"),
            "daily_breakdown": [],
            "segments": [],
            "transactions": [],
            "total_due": Decimal("0.00")
        }

        if not from_date:
            return statement

        # Calculate loan age in days (inclusive of statement date)
        loan_age_days = (on_date - from_date).days + 1

        # FIXED: Cap at maximum 1095 days (3 * 365) to prevent going beyond 36 months
        max_loan_days = 3 * DAYS_IN_YEAR  # 1095 days
        if loan_age_days > max_loan_days:
            loan_age_days = max_loan_days
            # Adjust on_date to match the maximum allowed date (day 1095)
            on_date = from_date + timezone.timedelta(days=max_loan_days - 1)

        current_principal = principal
        transaction_dates = {}

        # Process transactions
        for tx in transactions:
            tx_date = tx.transaction_date.date()
            if tx_date <= on_date:
                transaction_dates.setdefault(tx_date, []).append({
                    'amount': tx.amount,
                    'description': tx.description or ""
                })
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
        base_amount_after_yearly = current_principal + yearly_interest

        # FIXED: Use exactly 365 days for first year
        if loan_age_days <= DAYS_IN_YEAR:
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

            # Process each transaction separately within first year
            running_total = base_amount_after_yearly

            for tx_date, transactions_list in transaction_dates.items():
                if tx_date <= on_date:
                    for tx_data in transactions_list:
                        payment_amount = tx_data['amount']
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
                            "note": f"Payment of {payment_amount} - {tx_data['description']}"
                        })

        else:
            # After first year - show yearly interest, then simple daily interest from day 366+
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

            # Process payments within first year (each transaction separately)
            first_year_cutoff = from_date + timezone.timedelta(days=DAYS_IN_YEAR)

            for tx_date, transactions_list in transaction_dates.items():
                if tx_date < first_year_cutoff:
                    for tx_data in transactions_list:
                        payment_amount = tx_data['amount']
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
                            "note": f"Payment of {payment_amount} - {tx_data['description']}"
                        })

            # Days 366+: Simple daily interest on remaining principal
            daily_interest_total = Decimal("0.00")

            for day in range(DAYS_IN_YEAR + 1, loan_age_days + 1):
                current_date = from_date + timezone.timedelta(days=day - 1)
                if current_date > on_date:
                    break

                # Check if loan is settled and this date is after settlement
                if self.loan.is_settled and self.loan.settled_date:
                    settled_date = self.loan.settled_date.date() if hasattr(self.loan.settled_date,
                                                                            'date') else self.loan.settled_date
                    if current_date > settled_date:
                        break

                # FIRST: Apply daily simple interest on current principal
                daily_interest = current_principal * (self.daily_fee_after_year_percentage / Decimal("100"))
                daily_interest_total += daily_interest
                running_total += daily_interest

                statement["daily_breakdown"].append({
                    "day": day,
                    "date": current_date,
                    "type": "Daily Simple Interest",
                    "principal": current_principal,
                    "interest_rate": f"{self.daily_fee_after_year_percentage}%",
                    "interest_amount": daily_interest,
                    "running_total": running_total,
                    "note": f"Simple interest: {current_principal} × {self.daily_fee_after_year_percentage}%"
                })

                # THEN: Process payments (reducing principal for next day's interest calculation)
                if current_date in transaction_dates:
                    for tx_data in transaction_dates[current_date]:
                        payment_amount = tx_data['amount']
                        running_total -= payment_amount
                        current_principal -= payment_amount

                        statement["daily_breakdown"].append({
                            "day": day,
                            "date": current_date,
                            "type": "Payment",
                            "principal": current_principal,
                            "payment_amount": payment_amount,
                            "running_total": running_total,
                            "note": f"Payment of {payment_amount} - {tx_data['description']}"
                        })

            statement["daily_interest_total"] = daily_interest_total

        # Exit fee on statement date
        principal_start_of_day = current_principal
        if on_date in transaction_dates:
            for tx_data in transaction_dates[on_date]:
                principal_start_of_day += tx_data['amount']

        exit_fee = principal_start_of_day * self.exit_fee_percentage / Decimal("100")
        statement["exit_fee"] = exit_fee

        # Add exit fee to final total
        final_total = running_total + exit_fee
        statement["total_due"] = final_total

        # Add exit fee to breakdown
        statement["daily_breakdown"].append({
            "day": loan_age_days,
            "date": on_date,
            "type": "Exit Fee",
            "principal": principal_start_of_day,
            "interest_rate": f"{self.exit_fee_percentage}%",
            "interest_amount": exit_fee,
            "running_total": final_total,
            "note": f"Exit fee: {principal_start_of_day} × {self.exit_fee_percentage}% (calculated on start-of-day principal)"
        })

        # Create segments for compatibility
        total_payments_made = sum(tx['amount'] for tx in statement["transactions"])
        segment_total = total_payments_made + final_total

        statement["segments"] = [{
            "start": from_date,
            "end": on_date,
            "principal": self.initial_amount,
            "first_year_interest": statement["yearly_interest"],
            "daily_interest_accumulated": statement["daily_interest_total"],
            "exit_fee": statement["exit_fee"],
            "total_interest": statement["yearly_interest"] + statement["daily_interest_total"],
            "total_payments_made": total_payments_made,
            "total": segment_total
        }]

        # Summary
        statement["summary"] = {
            "loan_age_days": loan_age_days,
            "within_first_year": loan_age_days <= DAYS_IN_YEAR,
            "base_principal": current_principal,
            "yearly_interest": statement["yearly_interest"],
            "daily_interest_total": statement["daily_interest_total"],
            "exit_fee": exit_fee,
            "total_due": final_total
        }

        # Add settlement info to statement if loan is settled
        if self.loan.is_settled and self.loan.settled_date:
            settled_date = self.loan.settled_date.date() if hasattr(self.loan.settled_date,
                                                                    'date') else self.loan.settled_date
            statement["is_settled"] = True
            statement["settled_date"] = settled_date

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

        return statement

    @property
    def id(self):
        """Return the loan ID for compatibility"""
        return self.loan.id

    def __str__(self):
        return f"LoanBook for Loan #{self.loan.id}"
