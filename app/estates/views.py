from rest_framework import viewsets, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from core.models import Application
from core.models import *
from .serializers import *


# Individual ViewSets (update/create/delete per model)
class RealAndLeaseholdViewSet(viewsets.ModelViewSet):
    queryset = RealAndLeaseholdProperty.objects.all()
    serializer_class = RealAndLeaseholdSerializer
    permission_classes = [permissions.IsAuthenticated]


class HouseholdContentsViewSet(viewsets.ModelViewSet):
    queryset = HouseholdContents.objects.all()
    serializer_class = HouseholdContentsSerializer
    permission_classes = [permissions.IsAuthenticated]


class CarsBoatsViewSet(viewsets.ModelViewSet):
    queryset = CarsBoats.objects.all()
    serializer_class = CarsBoatsSerializer
    permission_classes = [permissions.IsAuthenticated]


class BusinessFarmingViewSet(viewsets.ModelViewSet):
    queryset = BusinessFarming.objects.all()
    serializer_class = BusinessFarmingSerializer
    permission_classes = [permissions.IsAuthenticated]


class BusinessOtherViewSet(viewsets.ModelViewSet):
    queryset = BusinessOther.objects.all()
    serializer_class = BusinessOtherSerializer
    permission_classes = [permissions.IsAuthenticated]


class UnpaidPurchaseMoneyViewSet(viewsets.ModelViewSet):
    queryset = UnpaidPurchaseMoney.objects.all()
    serializer_class = UnpaidPurchaseMoneySerializer
    permission_classes = [permissions.IsAuthenticated]


class FinancialAssetViewSet(viewsets.ModelViewSet):
    queryset = FinancialAsset.objects.all()
    serializer_class = FinancialAssetSerializer
    permission_classes = [permissions.IsAuthenticated]


class LifeInsuranceViewSet(viewsets.ModelViewSet):
    queryset = LifeInsurance.objects.all()
    serializer_class = LifeInsuranceSerializer
    permission_classes = [permissions.IsAuthenticated]


class DebtOwedViewSet(viewsets.ModelViewSet):
    queryset = DebtOwed.objects.all()
    serializer_class = DebtOwedSerializer
    permission_classes = [permissions.IsAuthenticated]


class SecuritiesQuotedViewSet(viewsets.ModelViewSet):
    queryset = SecuritiesQuoted.objects.all()
    serializer_class = SecuritiesQuotedSerializer
    permission_classes = [permissions.IsAuthenticated]


class SecuritiesUnquotedViewSet(viewsets.ModelViewSet):
    queryset = SecuritiesUnquoted.objects.all()
    serializer_class = SecuritiesUnquotedSerializer
    permission_classes = [permissions.IsAuthenticated]


class OtherPropertyViewSet(viewsets.ModelViewSet):
    queryset = OtherProperty.objects.all()
    serializer_class = OtherPropertySerializer
    permission_classes = [permissions.IsAuthenticated]


class IrishDebtViewSet(viewsets.ModelViewSet):
    queryset = IrishDebt.objects.all()
    serializer_class = IrishDebtSerializer
    permission_classes = [permissions.IsAuthenticated]


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
