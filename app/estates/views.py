from rest_framework import viewsets, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db import transaction
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from core.models import Application, Notification
from core.models import *
from .serializers import *


class BaseEstateViewSet(viewsets.ModelViewSet):
    """Base class for estate ViewSets with notification functionality"""
    permission_classes = [permissions.IsAuthenticated]

    def get_estate_type_name(self):
        """Override in subclasses to return human-readable estate type name"""
        return self.__class__.__name__.replace('ViewSet', '').replace('_', ' ')

    def send_estate_notification(self, action, estate_instance, changes=None):
        """Send notification for estate operations"""
        if not hasattr(estate_instance, 'application') or not estate_instance.application:
            return

        assigned_to_user = estate_instance.application.assigned_to
        if not assigned_to_user:
            return

        estate_type = self.get_estate_type_name()

        # Create simple action-specific message
        if action == 'created':
            message = f'New {estate_type} added to application'
        elif action == 'updated':
            if changes:
                change_details = "; ".join(changes)
                message = f'{estate_type} updated: {change_details}'
            else:
                message = f'{estate_type} updated'
        elif action == 'deleted':
            message = f'{estate_type} removed from application'
        else:
            message = f'{estate_type} {action}'

        # Create notification with detailed message
        notification = Notification.objects.create(
            recipient=assigned_to_user,
            text=message,
            seen=False,
            created_by=self.request.user,
            application=estate_instance.application
        )

        # Prepare payload with detailed message
        payload = {
            'type': 'notification',
            'message': notification.text,  # This now contains all the detailed info
            'recipient': notification.recipient.email if notification.recipient else None,
            'notification_id': notification.id,
            'application_id': estate_instance.application.id,
            'seen': notification.seen,
            'country': estate_instance.application.user.country,
            'estate_type': estate_type,
            'estate_action': action,
        }

        # Add detailed changes array for frontend processing if needed
        if action == 'updated' and changes:
            payload['changes'] = changes

        # Send via channels
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)('broadcast', payload)

        return notification

    def compare_instances(self, original_data, updated_data):
        """Compare original and updated instance data to find changes with actual values"""
        changes = []
        exclude_fields = ['_state', 'id', 'created_at', 'updated_at', 'last_updated_by']

        for field, original_value in original_data.items():
            if field not in exclude_fields and field in updated_data:
                updated_value = updated_data[field]
                if original_value != updated_value:
                    # Convert field name to human readable
                    field_name = field.replace('_', ' ').title()
                    # Include actual values in the change description
                    changes.append(f"{field_name} changed from '{original_value}' to '{updated_value}'")

        return changes

    @transaction.atomic
    def perform_create(self, serializer):
        """Handle create with notification"""
        serializer.save()
        self.send_estate_notification('created', serializer.instance)

    @transaction.atomic
    def perform_update(self, serializer):
        """Handle update with notification"""
        # Get original data before update
        original_instance = self.get_object()
        original_data = original_instance.__dict__.copy()

        # Save the update
        serializer.save()

        # Get updated data
        updated_data = serializer.instance.__dict__.copy()

        # Find changes
        changes = self.compare_instances(original_data, updated_data)

        # Send notification only if there are actual changes
        if changes:
            self.send_estate_notification('updated', serializer.instance, changes)

    @transaction.atomic
    def perform_destroy(self, instance):
        """Handle delete with notification"""
        # Send notification before deletion
        self.send_estate_notification('deleted', instance)
        instance.delete()


# Individual ViewSets with custom estate type names
class RealAndLeaseholdViewSet(BaseEstateViewSet):
    queryset = RealAndLeaseholdProperty.objects.all()
    serializer_class = RealAndLeaseholdSerializer

    def get_estate_type_name(self):
        return "Real & Leasehold Property"


class HouseholdContentsViewSet(BaseEstateViewSet):
    queryset = HouseholdContents.objects.all()
    serializer_class = HouseholdContentsSerializer

    def get_estate_type_name(self):
        return "Household Contents"


class CarsBoatsViewSet(BaseEstateViewSet):
    queryset = CarsBoats.objects.all()
    serializer_class = CarsBoatsSerializer

    def get_estate_type_name(self):
        return "Cars & Boats"


class BusinessFarmingViewSet(BaseEstateViewSet):
    queryset = BusinessFarming.objects.all()
    serializer_class = BusinessFarmingSerializer

    def get_estate_type_name(self):
        return "Business Farming Interest"


class BusinessOtherViewSet(BaseEstateViewSet):
    queryset = BusinessOther.objects.all()
    serializer_class = BusinessOtherSerializer

    def get_estate_type_name(self):
        return "Other Business Interest"


class UnpaidPurchaseMoneyViewSet(BaseEstateViewSet):
    queryset = UnpaidPurchaseMoney.objects.all()
    serializer_class = UnpaidPurchaseMoneySerializer

    def get_estate_type_name(self):
        return "Unpaid Purchase Money"


class FinancialAssetViewSet(BaseEstateViewSet):
    queryset = FinancialAsset.objects.all()
    serializer_class = FinancialAssetSerializer

    def get_estate_type_name(self):
        return "Financial Asset"


class LifeInsuranceViewSet(BaseEstateViewSet):
    queryset = LifeInsurance.objects.all()
    serializer_class = LifeInsuranceSerializer

    def get_estate_type_name(self):
        return "Life Insurance"


class DebtOwedViewSet(BaseEstateViewSet):
    queryset = DebtOwed.objects.all()
    serializer_class = DebtOwedSerializer

    def get_estate_type_name(self):
        return "Debt Owed to Estate"


class SecuritiesQuotedViewSet(BaseEstateViewSet):
    queryset = SecuritiesQuoted.objects.all()
    serializer_class = SecuritiesQuotedSerializer

    def get_estate_type_name(self):
        return "Quoted Securities"


class SecuritiesUnquotedViewSet(BaseEstateViewSet):
    queryset = SecuritiesUnquoted.objects.all()
    serializer_class = SecuritiesUnquotedSerializer

    def get_estate_type_name(self):
        return "Unquoted Securities"


class OtherPropertyViewSet(BaseEstateViewSet):
    queryset = OtherProperty.objects.all()
    serializer_class = OtherPropertySerializer

    def get_estate_type_name(self):
        return "Other Property"


class IrishDebtViewSet(BaseEstateViewSet):
    queryset = IrishDebt.objects.all()
    serializer_class = IrishDebtSerializer

    def get_estate_type_name(self):
        return "Irish Debt"


# 🔍 Unified read-only view by application
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def estates_by_application(request, application_id):
    application = get_object_or_404(Application, id=application_id)

    data = {
        "real_and_leasehold": RealAndLeaseholdSerializer(
            RealAndLeaseholdProperty.objects.filter(application=application), many=True).data,
        "household_contents": HouseholdContentsSerializer(
            HouseholdContents.objects.filter(application=application), many=True).data,
        "cars_boats": CarsBoatsSerializer(
            CarsBoats.objects.filter(application=application), many=True).data,
        "business_farming": BusinessFarmingSerializer(
            BusinessFarming.objects.filter(application=application), many=True).data,
        "business_other": BusinessOtherSerializer(
            BusinessOther.objects.filter(application=application), many=True).data,
        "unpaid_purchase_money": UnpaidPurchaseMoneySerializer(
            UnpaidPurchaseMoney.objects.filter(application=application), many=True).data,
        "financial_assets": FinancialAssetSerializer(
            FinancialAsset.objects.filter(application=application), many=True).data,
        "life_insurance": LifeInsuranceSerializer(
            LifeInsurance.objects.filter(application=application), many=True).data,
        "debts_owing": DebtOwedSerializer(
            DebtOwed.objects.filter(application=application), many=True).data,
        "securities_quoted": SecuritiesQuotedSerializer(
            SecuritiesQuoted.objects.filter(application=application), many=True).data,
        "securities_unquoted": SecuritiesUnquotedSerializer(
            SecuritiesUnquoted.objects.filter(application=application), many=True).data,
        "other_property": OtherPropertySerializer(
            OtherProperty.objects.filter(application=application), many=True).data,
        "irish_debts": IrishDebtSerializer(
            IrishDebt.objects.filter(application=application), many=True).data,
    }

    return Response(data)
