"""
viewsets for Loan api
"""
from django.utils import timezone
from drf_spectacular.utils import extend_schema_view, extend_schema, OpenApiParameter
from rest_framework import (viewsets, )
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status

from app.pagination import CustomPageNumberPagination
from .permissions import IsStaff

from core.models import Loan, Transaction, LoanExtension
from loan import serializers


@extend_schema_view(
    list=extend_schema(
        summary='Retrieve all transactions {-Works only for staff users-}',
        description='Returns  all transactions.',
        tags=['transactions'],
    ),
    retrieve=extend_schema(
        summary='Retrieve a transaction {-Works only for staff users-}',
        description='Returns detailed information about an transaction.',
        tags=['transactions'],
    ),

    create=extend_schema(
        summary='Create a new transaction {-Works only for staff users-}',
        description='Creates a new transaction and returns information about the created transaction.',
        tags=['transactions']
    ),

    update=extend_schema(
        summary='Update a transaction {-Works only for staff users-}',
        description='Updates an existing transaction and returns information about the updated transaction.',
        tags=['transactions']
    ),

    partial_update=extend_schema(
        summary='Partially update a transaction {-Works only for staff users-}',
        description='Partially updates an existing transaction and returns information about the updated transaction.',
        tags=['transactions']
    ),

    destroy=extend_schema(
        summary='Delete a transaction {-Works only for staff users-}',
        description='Deletes an existing transaction and does not return any content.',
        tags=['transactions']
    )
)
class TransactionViewSet(viewsets.ModelViewSet):
    """VIewset for Transaction Viewset"""
    authentication_classes = (JWTAuthentication,)
    permission_classes = [IsAuthenticated, IsStaff]
    queryset = Loan.objects.all()
    serializer_class = serializers.TransactionSerializer

    def get_queryset(self):
        return Transaction.objects.all().order_by('-id')

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


@extend_schema_view(
    list=extend_schema(
        summary='Retrieve all loan_extensions {-Works only for staff users-}',
        description='Returns  all loan_extensions.',
        tags=['loan_extensions'],
    ),
    retrieve=extend_schema(
        summary='Retrieve a loan_extension {-Works only for staff users-}',
        description='Returns detailed information about a loan_extension.',
        tags=['loan_extensions'],
    ),

    create=extend_schema(
        summary='Create a new loan_extension {-Works only for staff users-}',
        description='Creates a new loan_extension and returns information about the created loan_extension.',
        tags=['loan_extensions']
    ),

    update=extend_schema(
        summary='Update a loan_extension {-Works only for staff users-}',
        description='Updates an existing loan_extension and returns information about the updated loan_extension.',
        tags=['loan_extensions']
    ),

    partial_update=extend_schema(
        summary='Partially update an loan_extension {-Works only for staff users-}',
        description='Partially updates a existing loan_extension and returns information about the updated loan_extension.',
        tags=['loan_extensions']
    ),

    destroy=extend_schema(
        summary='Delete a loan_extension {-Works only for staff users-}',
        description='Deletes an existing loan_extension and does not return any content.',
        tags=['loan_extensions']
    )
)
class LoanExtensionViewSet(viewsets.ModelViewSet):
    """viewset for LoanExtension APIs"""
    queryset = LoanExtension.objects.all()
    authentication_classes = (JWTAuthentication,)
    permission_classes = [IsAuthenticated, IsStaff]
    serializer_class = serializers.LoanExtensionSerializer

    def get_queryset(self):
        return LoanExtension.objects.all().order_by('-id')

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


@extend_schema_view(
    list=extend_schema(
        summary='Retrieve all loans {-Works only for staff users-}',
        description='Returns  all loans.',
        tags=['loans'],
        parameters=[
            OpenApiParameter(name='status',
                             description='Filter by application status - optional (active,settled)',
                             required=False, type=str),
        ]
    ),
    retrieve=extend_schema(
        summary='Retrieve a loan {-Works only for staff users-}',
        description='Returns detailed information about a loan.',
        tags=['loans'],
    ),

    create=extend_schema(
        summary='Create a new loan {-Works only for staff users-}',
        description='Creates a new loan and returns information about the created loan.',
        tags=['loans']
    ),

    update=extend_schema(
        summary='Update a loan {-Works only for staff users-}',
        description='Updates an existing loan and returns information about the updated loan.',
        tags=['loans']
    ),

    partial_update=extend_schema(
        summary='Partially update a loan {-Works only for staff users-}',
        description='Partially updates an existing loan and returns information about the updated loan.',
        tags=['loans']
    ),

    destroy=extend_schema(
        summary='Delete a loan {-Works only for staff users-}',
        description='Deletes an existing loan and does not return any content.',
        tags=['loans']
    )
)
class LoanViewSet(viewsets.ModelViewSet):
    """View for manage Loan Apis"""
    authentication_classes = (JWTAuthentication,)
    permission_classes = [IsAuthenticated, IsStaff]
    queryset = Loan.objects.all()
    serializer_class = serializers.LoanSerializer
    pagination_class = CustomPageNumberPagination

    def get_queryset(self):
        queryset = self.queryset

        stat = self.request.query_params.get('status', None)
        assigned = self.request.query_params.get('assigned', None)
        old_to_new = self.request.query_params.get('old_to_new', None)

        if assigned is not None:
            if assigned.lower() == "true":
                queryset = queryset.filter(application__assigned_to=self.request.user)
            if assigned.lower() == "false":
                queryset = queryset.filter(application__assigned_to=None)

        if stat is not None:
            if stat == 'active':
                queryset = queryset.filter(is_settled=False)
            elif stat == 'settled':
                queryset = queryset.filter(is_settled=True)

        if old_to_new is not None:
            if old_to_new == "true":
                return queryset.order_by('id')
        else:
            return queryset.order_by('-id')

    def perform_create(self, serializer):
        serializer.save(approved_by=self.request.user)
        serializer.save(approved_date=timezone.now().date())

    def perform_update(self, serializer):
        serializer.save(last_updated_by=self.request.user)


@extend_schema_view(
    retrieve=extend_schema(
        summary='Retrieve a loan by application ID {-Accessible to non-staff users-}',
        description='Returns the loan associated with a specific application ID. All fields are read-only.',
        tags=['loans']
    )
)
class ReadOnlyLoanViewSet(viewsets.ReadOnlyModelViewSet):
    """View for read-only access to Loan by application ID"""
    queryset = Loan.objects.all()
    serializer_class = serializers.LoanSerializer
    authentication_classes = (JWTAuthentication,)
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary='Retrieve a loan by application ID',
        description='Returns loan details based on the application ID. This endpoint is accessible to non-staff users.',
        tags=['loans']
    )
    def loan_by_application(self, request, application_id=None):
        try:
            loan = Loan.objects.get(application__id=application_id)

            # If the user is not a staff member, check if the application belongs to them
            if not request.user.is_staff:
                if loan.application.user != request.user:
                    return Response({'detail': 'You do not have permission to access this loan.'},
                                    status=status.HTTP_403_FORBIDDEN)

            serializer = self.get_serializer(loan)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Loan.DoesNotExist:
            return Response({'detail': 'Loan not found.'}, status=status.HTTP_404_NOT_FOUND)
