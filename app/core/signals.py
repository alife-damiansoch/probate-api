from decimal import Decimal

from django.db.models.signals import post_save
from django.dispatch import receiver
from core.models import Loan
from loanbook.models import LoanBook


@receiver(post_save, sender=Loan)
def create_loanbook_on_paid_out(sender, instance, **kwargs):
    if (instance.is_paid_out and
            instance.paid_out_date and
            instance.paid_out_date != "" and
            not hasattr(instance, 'loanbook')):
        application = instance.application
        estate_value = application.value_of_the_estate_after_expenses() if application else Decimal("0.00")

        LoanBook.objects.create(
            loan=instance,
            initial_amount=instance.amount_agreed,
            estate_net_value=estate_value,
            created_at=instance.paid_out_date
        )
