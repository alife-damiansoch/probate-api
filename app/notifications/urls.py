from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import NotificationViewSet  # Make sure to import the new viewset

router = DefaultRouter()
app_name = 'notification'

# Register the Notification viewset with the router
router.register(r'applications/notifications', NotificationViewSet, basename='notification')

urlpatterns = [
    path('', include(router.urls)),
    # other specific endpoints
]
