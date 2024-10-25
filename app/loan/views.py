"""
viewsets for Loan api
"""
from datetime import datetime

from django.db.models import Sum
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_view, extend_schema, OpenApiParameter
from rest_framework import (viewsets, )
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAuthenticated

import agents_loan.serializers as AgentLoanSerializers
from app.pagination import CustomPageNumberPagination
from .permissions import IsStaff

from core.models import Loan, Transaction, LoanExtension
from loan import serializers

from dateutil.relativedelta import relativedelta
from django.db.models import Sum, F, ExpressionWrapper
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework import status
from django.db.models import DateField
from django.db.models.functions import Cast


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
        description='Returns all loans with optional filters for status, assignment, payout status, and sorting.',
        tags=['loans'],
        parameters=[
            OpenApiParameter(
                name='status',
                description='Filter by loan status - optional (active, settled)',
                required=False,
                type=str
            ),
            OpenApiParameter(
                name='assigned',
                description='Filter by whether the loan is assigned to the logged-in user - optional (true, false)',
                required=False,
                type=str
            ),
            OpenApiParameter(
                name='old_to_new',
                description='Sort by loan ID from old to new (true) or new to old (default)',
                required=False,
                type=str
            ),
            OpenApiParameter(
                name='not_paid_out_only',
                description='Filter loans that are not paid out - optional (true, false)',
                required=False,
                type=str
            ),
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
    """View for managing Loan APIs"""
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
        not_paid_out_only = self.request.query_params.get('not_paid_out_only', None)

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

        if not_paid_out_only is not None:
            if not_paid_out_only.lower() == "true":
                queryset = queryset.filter(is_paid_out=False)

        if old_to_new is not None:
            if old_to_new == "true":
                return queryset.order_by('id')
        else:
            return queryset.order_by('-id')

        return queryset

    def perform_create(self, serializer):
        serializer.save(approved_by=self.request.user)
        serializer.save(approved_date=timezone.now().date())

    def perform_update(self, serializer):
        serializer.save(last_updated_by=self.request.user)

    @extend_schema(
        summary='Advanced search for loans {-Works only for staff users-}',
        description='Search loans with optional filters for amount, fee, term, status, settled date, paid out date, maturity date, extension fees, and related application fields.',
        tags=['loans'],
        parameters=[

            # Range filters for loan fields
            OpenApiParameter(name='from_amount_agreed', description='Filter by minimum agreed amount', required=False,
                             type=float),
            OpenApiParameter(name='to_amount_agreed', description='Filter by maximum agreed amount', required=False,
                             type=float),
            OpenApiParameter(name='from_fee_agreed', description='Filter by minimum agreed fee', required=False,
                             type=float),
            OpenApiParameter(name='to_fee_agreed', description='Filter by maximum agreed fee', required=False,
                             type=float),
            OpenApiParameter(name='from_term_agreed', description='Filter by minimum agreed term in months',
                             required=False, type=int),
            OpenApiParameter(name='to_term_agreed', description='Filter by maximum agreed term in months',
                             required=False, type=int),
            OpenApiParameter(name='from_settled_date', description='Start date range for settled_date', required=False,
                             type=OpenApiTypes.DATE),
            OpenApiParameter(name='to_settled_date', description='End date range for settled_date', required=False,
                             type=OpenApiTypes.DATE),
            OpenApiParameter(name='from_paid_out_date', description='Start date range for paid_out_date',
                             required=False, type=OpenApiTypes.DATE),
            OpenApiParameter(name='to_paid_out_date', description='End date range for paid_out_date', required=False,
                             type=OpenApiTypes.DATE),
            OpenApiParameter(name='from_maturity_date', description='Start date range for maturity_date',
                             required=False, type=OpenApiTypes.DATE),
            OpenApiParameter(name='to_maturity_date', description='End date range for maturity_date', required=False,
                             type=OpenApiTypes.DATE),

            # Boolean filters for loan fields
            OpenApiParameter(name='is_settled', description='Filter by settled status (true/false)', required=False,
                             type=bool),
            OpenApiParameter(name='is_paid_out', description='Filter by paid out status (true/false)', required=False,
                             type=bool),

            # Extension fees filter for loan
            OpenApiParameter(name='extension_fees_gt_zero',
                             description='Filter loans with extension fees greater than 0', required=False, type=bool),

            # Foreign key filters from Application model
            OpenApiParameter(name='application_user_id', description='Filter by application user ID', required=False,
                             type=int),
            OpenApiParameter(name='application_solicitor_id', description='Filter by application solicitor ID',
                             required=False, type=int),
            OpenApiParameter(name='application_assigned_to_id', description='Filter by application assigned to user ID',
                             required=False, type=int),
        ]
    )
    @action(detail=False, methods=['get'], url_path='search-advanced-loans')
    def search_advanced_loans(self, request):
        """
        Search loans based on various model fields, supporting filtering and sorting.
        """
        queryset = self.queryset

        # Amount, fee, term filtering
        from_amount_agreed = request.query_params.get('from_amount_agreed')
        to_amount_agreed = request.query_params.get('to_amount_agreed')
        if from_amount_agreed and to_amount_agreed:
            queryset = queryset.filter(amount_agreed__gte=from_amount_agreed, amount_agreed__lte=to_amount_agreed)

        from_fee_agreed = request.query_params.get('from_fee_agreed')
        to_fee_agreed = request.query_params.get('to_fee_agreed')
        if from_fee_agreed and to_fee_agreed:
            queryset = queryset.filter(fee_agreed__gte=from_fee_agreed, fee_agreed__lte=to_fee_agreed)

        from_term_agreed = request.query_params.get('from_term_agreed')
        to_term_agreed = request.query_params.get('to_term_agreed')
        if from_term_agreed and to_term_agreed:
            queryset = queryset.filter(term_agreed__gte=from_term_agreed, term_agreed__lte=to_term_agreed)

        # Date filtering: from and to for 'settled_date', 'paid_out_date'
        from_settled_date = request.query_params.get('from_settled_date')
        to_settled_date = request.query_params.get('to_settled_date')
        if from_settled_date and to_settled_date:
            queryset = queryset.filter(settled_date__range=[from_settled_date, to_settled_date])

        from_paid_out_date = request.query_params.get('from_paid_out_date')
        to_paid_out_date = request.query_params.get('to_paid_out_date')
        if from_paid_out_date and to_paid_out_date:
            queryset = queryset.filter(paid_out_date__range=[from_paid_out_date, to_paid_out_date])

        # Boolean filters
        is_settled = request.query_params.get('is_settled')
        if is_settled is not None:
            queryset = queryset.filter(is_settled=(is_settled.lower() == 'true'))

        is_paid_out = request.query_params.get('is_paid_out')
        if is_paid_out is not None:
            queryset = queryset.filter(is_paid_out=(is_paid_out.lower() == 'true'))

        # Extension fees filter (check if LoanExtension exists for a loan)
        extension_fees_gt_zero = request.query_params.get('extension_fees_gt_zero')
        if extension_fees_gt_zero and extension_fees_gt_zero.lower() == 'true':
            queryset = queryset.filter(extensions__isnull=False)
        elif extension_fees_gt_zero and extension_fees_gt_zero.lower() == 'false':
            queryset = queryset.filter(extensions__isnull=True)

        # Application-related filters
        application_user_id = request.query_params.get('application_user_id')
        if application_user_id:
            queryset = queryset.filter(application__user_id=application_user_id)

        application_solicitor_id = request.query_params.get('application_solicitor_id')
        if application_solicitor_id:
            queryset = queryset.filter(application__solicitor_id=application_solicitor_id)

        application_assigned_to_id = request.query_params.get('application_assigned_to_id')
        if application_assigned_to_id:
            queryset = queryset.filter(application__assigned_to_id=application_assigned_to_id)

        # Maturity date filtering (handled manually)
        from_maturity_date = request.query_params.get('from_maturity_date')
        to_maturity_date = request.query_params.get('to_maturity_date')

        if from_maturity_date or to_maturity_date:
            filtered_loans = []
            for loan in queryset:
                if loan.paid_out_date:
                    # Sum the total extension term
                    extensions_term_sum = loan.extensions.aggregate(total_extension_term=Sum('extension_term_months'))[
                                              'total_extension_term'] or 0

                    # Calculate maturity date based on paid_out_date
                    maturity_date = loan.paid_out_date + relativedelta(months=loan.term_agreed + extensions_term_sum)

                    # Filter based on maturity date
                    if from_maturity_date and to_maturity_date:
                        if from_maturity_date <= maturity_date.strftime('%Y-%m-%d') <= to_maturity_date:
                            filtered_loans.append(loan)
                    elif from_maturity_date and maturity_date.strftime('%Y-%m-%d') >= from_maturity_date:
                        filtered_loans.append(loan)
                    elif to_maturity_date and maturity_date.strftime('%Y-%m-%d') <= to_maturity_date:
                        filtered_loans.append(loan)

            queryset = queryset.filter(pk__in=[loan.pk for loan in filtered_loans])

        # Optimize related object fetching with select_related and prefetch_related
        queryset = queryset.select_related('application').prefetch_related('extensions')

        # Remove duplicate loans from the queryset
        queryset = queryset.distinct()

        # Sorting
        queryset = queryset.order_by('-id')

        # Serialize the loan data
        loan_serializer = serializers.LoanSerializer(queryset, many=True)

        # Create a list to hold the response with additional application data
        response_data = []
        for loan in loan_serializer.data:
            application_instance = Loan.objects.get(pk=loan['id']).application
            application_serializer = AgentLoanSerializers.AgentApplicationDetailSerializer(application_instance)
            loan['application_details'] = application_serializer.data
            response_data.append(loan)

        return Response(response_data, status=status.HTTP_200_OK)


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
