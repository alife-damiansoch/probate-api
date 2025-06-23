from rest_framework import serializers
from .models import LoanBook
from django.utils import timezone
import datetime


class LoanBookSerializer(serializers.ModelSerializer):
    total_due = serializers.SerializerMethodField()
    statement = serializers.SerializerMethodField()

    class Meta:
        model = LoanBook
        fields = [
            'loan', 'initial_amount', 'estate_net_value',
            'initial_fee_percentage', 'daily_fee_after_year_percentage', 'exit_fee_percentage',
            'created_at', 'total_due', 'statement'
        ]

    def get_total_due(self, obj):
        return obj.calculate_total_due()

    def get_statement(self, obj):
        request = self.context.get("request")
        date_param = request.query_params.get("on_date") if request else None
        try:
            on_date = datetime.datetime.strptime(date_param, "%Y-%m-%d").date() if date_param else None
        except Exception:
            on_date = None
        return obj.generate_statement(on_date)
