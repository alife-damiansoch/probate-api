from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ExpenseViewSet

router = DefaultRouter()
app_name = 'expense'
router.register(r'expenses', ExpenseViewSet, basename='expense')
urlpatterns = [
    path('', include(router.urls)),
]
