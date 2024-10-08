# agents_default_assignments/urls.py

from django.urls import path
from .views import (
    AssignmentListCreateView,
    AssignmentRetrieveUpdateDestroyView,
    StaffUserAssignedAgenciesView,
    AgencyAssignedStaffView,
)

app_name = 'assignments'

urlpatterns = [
    path('assignments/', AssignmentListCreateView.as_view(), name='assignments-list'),
    path('assignments/<int:pk>/', AssignmentRetrieveUpdateDestroyView.as_view(), name='assignments-detail'),
    path('staff/<int:staff_user_id>/assigned-agencies/', StaffUserAssignedAgenciesView.as_view(),
         name='staff-assigned-agencies'),
    path('agency/<int:agency_user_id>/assigned-staff/', AgencyAssignedStaffView.as_view(),
         name='agency-assigned-staff'),
]
