from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from agents_loan.permissions import IsStaff
from core.models import Assignment
from .serializers import AssignmentSerializer, CreateAssignmentSerializer
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes
from rest_framework_simplejwt.authentication import JWTAuthentication


class AssignmentListCreateView(generics.ListCreateAPIView):
    """View for listing and creating assignments."""
    queryset = Assignment.objects.all()
    authentication_classes = (JWTAuthentication,)
    permission_classes = [IsAuthenticated, IsStaff]

    @extend_schema(
        summary='List Assignments',
        description='Lists all existing assignments between staff and agencies.',
        tags=['Assignments'],
    )
    def get(self, request, *args, **kwargs):
        """Retrieve a list of all assignments."""
        return super().get(request, *args, **kwargs)

    @extend_schema(
        summary='Create a New Assignment',
        description='Creates a new assignment linking a staff user to an agency.',
        request=CreateAssignmentSerializer,  # Specify the request serializer
        responses={201: AssignmentSerializer},  # Define the response serializer
        tags=['Assignments'],
    )
    def post(self, request, *args, **kwargs):
        """Create a new assignment."""
        return super().post(request, *args, **kwargs)

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return CreateAssignmentSerializer
        return AssignmentSerializer


class AssignmentRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    """View for retrieving, updating, or deleting a specific assignment."""
    queryset = Assignment.objects.all()
    authentication_classes = (JWTAuthentication,)
    permission_classes = [IsAuthenticated, IsStaff]

    @extend_schema(
        summary='Retrieve an Assignment',
        description='Returns detailed information about a specific assignment.',
        tags=['Assignments'],
    )
    def get(self, request, *args, **kwargs):
        """Retrieve a specific assignment by its ID."""
        return super().get(request, *args, **kwargs)

    @extend_schema(
        summary='Update an Assignment',
        description='Updates an existing assignment linking a staff user to an agency.',
        request=CreateAssignmentSerializer,  # Specify the request serializer
        responses={200: AssignmentSerializer},  # Define the response serializer
        tags=['Assignments'],
    )
    def put(self, request, *args, **kwargs):
        """Update an assignment with new data."""
        return super().put(request, *args, **kwargs)

    @extend_schema(
        summary='Partially Update an Assignment',
        description='Partially updates an existing assignment between staff and agencies.',
        request=CreateAssignmentSerializer,  # Specify the request serializer
        responses={200: AssignmentSerializer},  # Define the response serializer
        tags=['Assignments'],
    )
    def patch(self, request, *args, **kwargs):
        """Partially update an assignment."""
        return super().patch(request, *args, **kwargs)

    @extend_schema(
        summary='Delete an Assignment',
        description='Deletes an existing assignment between staff and agencies.',
        tags=['Assignments'],
    )
    def delete(self, request, *args, **kwargs):
        """Delete an assignment."""
        return super().delete(request, *args, **kwargs)

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return CreateAssignmentSerializer
        return AssignmentSerializer


class StaffUserAssignedAgenciesView(generics.ListAPIView):
    """View for listing all agencies assigned to a specific staff user."""
    serializer_class = AssignmentSerializer
    authentication_classes = (JWTAuthentication,)
    permission_classes = [IsAuthenticated, IsStaff]

    @extend_schema(
        summary='List Agencies Assigned to a Specific Staff User',
        description='Returns a list of agencies assigned to a specified staff user.',

        tags=['Assignments'],
    )
    def get(self, request, *args, **kwargs):
        """Retrieve agencies assigned to a specific staff user."""
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        """Filter the queryset to include only agencies assigned to the current staff user."""
        staff_user_id = self.kwargs['staff_user_id']
        return Assignment.objects.filter(staff_user_id=staff_user_id)


class AgencyAssignedStaffView(generics.ListAPIView):
    """View for listing the staff user a specific agency is assigned to."""
    serializer_class = AssignmentSerializer
    authentication_classes = (JWTAuthentication,)
    permission_classes = [IsAuthenticated, IsStaff]

    @extend_schema(
        summary='List Staff User Assigned to a Specific Agency',
        description='Returns the staff user that a specified agency is assigned to.',
        tags=['Assignments'],
    )
    def get(self, request, *args, **kwargs):
        """Retrieve staff user assigned to a specific agency."""
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        """Filter the queryset to include only the staff user assigned to the current agency."""
        agency_user_id = self.kwargs['agency_user_id']
        return Assignment.objects.filter(agency_user_id=agency_user_id)
