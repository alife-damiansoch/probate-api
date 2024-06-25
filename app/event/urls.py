from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import EventViewSet, EventByApplicationViewSet

router = DefaultRouter()
app_name = 'event'
router.register(r'events', EventViewSet, basename='events')
urlpatterns = [
    path('', include(router.urls)),
    # your specific endpoint
    path('events/<int:application_id>/', EventByApplicationViewSet.as_view({'get': 'list'}, ),
         name='events-by-application')
]
