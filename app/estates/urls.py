from rest_framework.routers import DefaultRouter
from django.urls import path, include
from . import views

router = DefaultRouter()
router.register(r"real_and_leasehold", views.RealAndLeaseholdViewSet)
router.register(r"household_contents", views.HouseholdContentsViewSet)
router.register(r"cars_boats", views.CarsBoatsViewSet)
router.register(r"business_farming", views.BusinessFarmingViewSet)
router.register(r"business_other", views.BusinessOtherViewSet)
router.register(r"unpaid_purchase_money", views.UnpaidPurchaseMoneyViewSet)
router.register(r"financial_assets", views.FinancialAssetViewSet)
router.register(r"life_insurance", views.LifeInsuranceViewSet)
router.register(r"debts_owing", views.DebtOwedViewSet)
router.register(r"securities_quoted", views.SecuritiesQuotedViewSet)
router.register(r"securities_unquoted", views.SecuritiesUnquotedViewSet)
router.register(r"other_property", views.OtherPropertyViewSet)
router.register(r"irish_debts", views.IrishDebtViewSet)

urlpatterns = [
    path("by_application/<int:application_id>/", views.estates_by_application, name="estates-by-application"),
    path("", include(router.urls)),
]
