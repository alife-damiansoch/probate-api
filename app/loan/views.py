"""
viewsets for Loan api
"""
from django.utils import timezone
from drf_spectacular.utils import extend_schema_view, extend_schema, OpenApiParameter
from rest_framework import (viewsets, )
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAuthenticated

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
        if stat is not None:
            if stat == 'active':
                queryset = queryset.filter(is_settled=False)
            elif stat == 'settled':
                queryset = queryset.filter(is_settled=True)
        return queryset.order_by('-id')

    def perform_create(self, serializer):
        serializer.save(approved_by=self.request.user)
        serializer.save(approved_date=timezone.now().date())

    def perform_update(self, serializer):
        serializer.save(last_updated_by=self.request.user)
