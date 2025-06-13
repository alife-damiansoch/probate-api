from rest_framework import serializers
from core.models import *


class RealAndLeaseholdSerializer(serializers.ModelSerializer):
    class Meta:
        model = RealAndLeaseholdProperty
        exclude = []  # or use 'fields = "__all__"'


class HouseholdContentsSerializer(serializers.ModelSerializer):
    class Meta:
        model = HouseholdContents
        exclude = []


class CarsBoatsSerializer(serializers.ModelSerializer):
    class Meta:
        model = CarsBoats
        exclude = []


class BusinessFarmingSerializer(serializers.ModelSerializer):
    class Meta:
        model = BusinessFarming
        exclude = []


class BusinessOtherSerializer(serializers.ModelSerializer):
    class Meta:
        model = BusinessOther
        exclude = []


class UnpaidPurchaseMoneySerializer(serializers.ModelSerializer):
    class Meta:
        model = UnpaidPurchaseMoney
        exclude = []


class FinancialAssetSerializer(serializers.ModelSerializer):
    class Meta:
        model = FinancialAsset
        exclude = []


class LifeInsuranceSerializer(serializers.ModelSerializer):
    class Meta:
        model = LifeInsurance
        exclude = []


class DebtOwedSerializer(serializers.ModelSerializer):
    class Meta:
        model = DebtOwed
        exclude = []


class SecuritiesQuotedSerializer(serializers.ModelSerializer):
    class Meta:
        model = SecuritiesQuoted
        exclude = []


class SecuritiesUnquotedSerializer(serializers.ModelSerializer):
    class Meta:
        model = SecuritiesUnquoted
        exclude = []


class OtherPropertySerializer(serializers.ModelSerializer):
    class Meta:
        model = OtherProperty
        exclude = []


class IrishDebtSerializer(serializers.ModelSerializer):
    class Meta:
        model = IrishDebt
        exclude = []
