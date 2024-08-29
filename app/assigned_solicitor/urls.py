from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AssignedSolicitorViewSet

router = DefaultRouter()
app_name = 'assigned_solicitor'

# Register the AssignedSolicitorViewSet with the router
router.register(r'applications/solicitors', AssignedSolicitorViewSet, basename='assigned_solicitor')

urlpatterns = [
    path('', include(router.urls)),
]
