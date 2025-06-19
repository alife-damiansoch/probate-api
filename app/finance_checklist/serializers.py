# serializers.py
from rest_framework import serializers
from .models import (
    Loan, FinanceChecklistItem, LoanChecklistSubmission,
    LoanChecklistItemCheck, ChecklistConfiguration
)


class ChecklistItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = FinanceChecklistItem
        fields = ['id', 'title', 'description', 'order']


class LoanChecklistItemCheckSerializer(serializers.ModelSerializer):
    checklist_item_title = serializers.CharField(source='checklist_item.title', read_only=True)

    class Meta:
        model = LoanChecklistItemCheck
        fields = ['checklist_item', 'checklist_item_title', 'is_checked', 'notes']


class LoanChecklistSubmissionSerializer(serializers.ModelSerializer):
    submitted_by_username = serializers.CharField(source='submitted_by.username', read_only=True)
    item_checks = LoanChecklistItemCheckSerializer(many=True, read_only=True)
    checked_items_count = serializers.SerializerMethodField()

    class Meta:
        model = LoanChecklistSubmission
        fields = [
            'id', 'submitted_by_username', 'submitted_at', 'notes',
            'item_checks', 'checked_items_count'
        ]

    def get_checked_items_count(self, obj):
        return obj.item_checks.filter(is_checked=True).count()


class LoanChecklistSerializer(serializers.ModelSerializer):
    checklist_submissions = LoanChecklistSubmissionSerializer(many=True, read_only=True)
    checklist_complete = serializers.SerializerMethodField()
    applicant_name = serializers.SerializerMethodField()

    class Meta:
        model = Loan
        fields = [
            'id', 'amount_agreed', 'approved_date', 'is_paid_out',
            'paid_out_date', 'applicant_name', 'checklist_complete',
            'checklist_submissions'
        ]

    def get_checklist_complete(self, obj):
        return obj.finance_checklist_complete

    def get_applicant_name(self, obj):
        return obj.first_applicant()


class ChecklistSubmissionDataSerializer(serializers.Serializer):
    """Serializer for checklist submission data"""
    checklist_items = serializers.ListField(
        child=serializers.DictField(
            child=serializers.CharField()
        ),
        required=True
    )
    notes = serializers.CharField(required=False, allow_blank=True)

    def validate_checklist_items(self, value):
        """Validate checklist items structure"""
        if not value:
            raise serializers.ValidationError("At least one checklist item is required.")

        for item in value:
            if 'item_id' not in item:
                raise serializers.ValidationError("Each item must have an 'item_id'.")

            try:
                int(item['item_id'])
            except (ValueError, TypeError):
                raise serializers.ValidationError("Item ID must be a valid integer.")

            if 'is_checked' not in item:
                raise serializers.ValidationError("Each item must have an 'is_checked' field.")

        return value
