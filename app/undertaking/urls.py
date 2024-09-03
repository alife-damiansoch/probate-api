from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import generate_undertaking_pdf  # Import the function-based view

router = DefaultRouter()
app_name = 'undertaking'

# Add the view to the router (if any ViewSets are registered in the future)
# router.register(r'undertakings', UndertakingViewSet, basename='undertaking')

urlpatterns = [
    path('', include(router.urls)),  # Include router URLs (empty in this case)
    path('generate-pdf/', generate_undertaking_pdf, name='generate_undertaking_pdf'),
    # Direct path for the function-based view
]
