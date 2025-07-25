"""
viewsets for Loan api
"""
from datetime import datetime

from django.db.models import Sum, Q
from django.utils import timezone
from django.db import transaction
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_view, extend_schema, OpenApiParameter, OpenApiTypes, OpenApiExample
from rest_framework import (viewsets, )
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAuthenticated

import agents_loan.serializers as AgentLoanSerializers
from app.pagination import CustomPageNumberPagination
from .permissions import IsStaff

from core.models import Loan, Transaction, LoanExtension, CommitteeApproval, Comment
from loan import serializers

from dateutil.relativedelta import relativedelta
from django.db.models import Sum, F, ExpressionWrapper
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework import status

from rest_framework.exceptions import ValidationError as DRFValidationError, PermissionDenied

from .utils import check_committee_approval, notify_application_referred_back_to_agent


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
        description='Returns all loans with optional filters for status, assignment, payout status, sorting, and applicant or ID search.',
        tags=['loans'],
        parameters=[
            OpenApiParameter(
                name='status',
                description='Filter by loan status - optional (active, paid_out, settled, not_committee_approved)',
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
            OpenApiParameter(
                name='awaiting_approval_only',
                description='Filter loans that are awaiting approval from the committee - optional (true, false)',
                required=False,
                type=str
            ),
            OpenApiParameter(
                name='search_term',
                description=(
                        'Search for loans based on applicant details - optional. '
                        'Supports partial matches for applicant first name, last name, or PPS number.'
                ),
                required=False,
                type=str
            ),
            OpenApiParameter(
                name='search_id',
                description='Search for a loan by its unique ID - optional. Must be a valid integer.',
                required=False,
                type=int
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
        awaiting_approval_only = self.request.query_params.get('awaiting_approval_only', None)
        search_term = self.request.query_params.get('search_term', None)
        search_id = self.request.query_params.get('search_id', None)

        user = self.request.user

        # Get the user's teams and filter based on the country
        country_filters = []
        if user.teams.filter(name='ie_team').exists():
            country_filters.append('IE')
        if user.teams.filter(name='uk_team').exists():
            country_filters.append('UK')

        # Check if no country filters were added
        if not country_filters:
            raise PermissionDenied("You must be assigned to at least one team to access this resource.")

        queryset = queryset.filter(application__user__country__in=country_filters)

        if search_id:
            try:
                search_id = int(search_id)  # Ensure search_id is an integer
                queryset = queryset.filter(id=search_id)
                return queryset
            except ValueError:
                raise DRFValidationError({"search_id": "Invalid ID. Must be an integer."})

                # Filter by applicant search term
        if search_term:
            queryset = queryset.filter(
                Q(application__applicants__first_name__icontains=search_term) |
                Q(application__applicants__last_name__icontains=search_term) |
                Q(application__applicants__pps_number__icontains=search_term)
            ).distinct()
            return queryset

        if assigned is not None:
            if assigned.lower() == "true":
                queryset = queryset.filter(application__assigned_to=self.request.user)
            if assigned.lower() == "false":
                queryset = queryset.filter(application__assigned_to=None)

        if stat is not None:
            if stat == 'active':
                queryset = queryset.filter(is_settled=False).exclude(
                    Q(is_committee_approved=False) | Q(is_paid_out=True, paid_out_date__isnull=False) | Q(
                        is_settled=True))
            elif stat == 'paid_out':
                queryset = queryset.filter(is_paid_out=True).exclude(is_settled=True).exclude(
                    paid_out_date__isnull=True  # EXCLUDE records where paid_out_date IS null
                )

                # Sort by maturity_date property using Python sorting
                # Since we've filtered out records with no paid_out_date, maturity_date should always exist
                queryset = sorted(queryset, key=lambda loan: loan.maturity_date)
                return queryset

            elif stat == 'settled':
                queryset = queryset.filter(is_settled=True)

            elif stat == 'not_committee_approved':
                queryset = queryset.filter(
                    Q(needs_committee_approval=True) & Q(is_committee_approved=False)
                ).exclude(is_committee_approved=None)

        if awaiting_approval_only is not None:
            if awaiting_approval_only.lower() == "true":
                queryset = queryset.filter(needs_committee_approval=True, is_committee_approved__isnull=True)

        if not_paid_out_only is not None:
            if not_paid_out_only.lower() == "true":
                # Not paid out means loans that are NOT truly paid out
                # (i.e., either is_paid_out=False OR paid_out_date is None)
                queryset = queryset.filter(
                    Q(is_paid_out=False) | Q(paid_out_date__isnull=True)
                ).exclude(
                    needs_committee_approval=True,
                    is_committee_approved=None,
                ).exclude(
                    needs_committee_approval=True,
                    is_committee_approved=False,
                )

        if old_to_new is not None:
            if old_to_new == "true":
                return queryset.order_by('id')
        else:
            return queryset.order_by('-id')

        return queryset

    def perform_create(self, serializer):
        serializer.save(
            approved_by=self.request.user,
            approved_date=timezone.now().date()
        )

    def perform_update(self, serializer):
        serializer.save(last_updated_by=self.request.user)

    @extend_schema(
        summary='Approve or Reject Loan {-Committee Members only-}',
        description='Allows committee members to approve or reject a loan. A rejection reason is required if rejecting.',
        tags=['loans'],
        request={
            'application/json': OpenApiTypes.OBJECT,
        },
        examples=[
            OpenApiExample(
                'Approve Loan',
                value={
                    'approved': True
                },
                description="Example request body for approving a loan."
            ),
            OpenApiExample(
                'Reject Loan with Reason',
                value={
                    'approved': False,
                    'rejection_reason': 'Insufficient documentation provided'
                },
                description="Example request body for rejecting a loan, with a required reason."
            )
        ],
        responses={200: OpenApiTypes.OBJECT}
    )
    @action(detail=True, methods=['post'])
    def approve_loan(self, request, pk=None):

        loan = self.get_object()
        member = request.user
        approved = request.data.get('approved')
        approved = approved.lower() == 'true' if isinstance(approved, str) else bool(approved)
        rejection_reason = request.data.get('rejection_reason')

        if not member.teams.filter(name="committee_members").exists():
            return Response(
                {"detail": "You are not authorized to approve this loan."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Ensure rejection reason is provided if loan is being rejected
        if not approved and rejection_reason is None:
            return Response(
                {"detail": "Rejection reason is required when rejecting a loan."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Register the approval or rejection
        approval, created = CommitteeApproval.objects.update_or_create(
            loan=loan, member=member,
            defaults={'approved': approved, 'rejection_reason': rejection_reason}
        )

        # Check if the loan now meets the approval or rejection requirements
        check_committee_approval(loan, request_user=request.user)
        return Response({"detail": "Your decision has been recorded."}, status=status.HTTP_200_OK)

    @extend_schema(
        summary='Refer Loan Back to Agent {-Committee Members only-}',
        description=(
                'Allows committee members to refer a loan back to the agent. This action sets '
                '`loan.application.approved` to `False`, deletes the loan, and logs the reason for referral '
                'provided in the `comment` field.'
        ),
        tags=['loans'],
        request={
            'application/json': OpenApiTypes.OBJECT
        },
        examples=[
            OpenApiExample(
                'Refer Loan Back Example',
                value={
                    'rejection_reason': 'The loan application is incomplete and requires additional information.'
                },
                description="Provide a comment explaining why the loan is referred back."
            )
        ],
        responses={200: OpenApiTypes.OBJECT, 403: OpenApiTypes.OBJECT, 400: OpenApiTypes.OBJECT}
    )
    @action(detail=True, methods=['post'])
    def refer_back_to_agent(self, request, pk=None):
        """
        Action to refer a loan back to the agent with an optional comment.
        """
        loan = self.get_object()
        member = request.user

        # Ensure the user is a committee member
        if not member.teams.filter(name="committee_members").exists():
            return Response(
                {"detail": "You are not authorized to perform this action."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Get the comment from the request
        comment = request.data.get('rejection_reason', '').strip()

        if not comment:
            return Response(
                {"detail": "A comment is required when referring back a loan."},
                status=status.HTTP_400_BAD_REQUEST
            )

        with transaction.atomic():
            # Add auto comment to the application
            logged_comment, created = Comment.objects.update_or_create(
                text=f"Application: {loan.application.id} referred back to the agent assigned. Reason: {comment}. User: {request.user.email}",
                created_by=member,
                is_important=True,
                application=loan.application,
            )

            # Create notification and send it real time to all agents
            notify_application_referred_back_to_agent(
                application=loan.application,
                request_user=request.user,
                comment=comment
            )

            # Create CommitteeApproval with the info about referring
            CommitteeApproval.objects.create(
                loan=loan,
                member=request.user,
                approved=False,
                rejection_reason=logged_comment.text
            )

            # Send email to all committee members that the loan was referred back
            success = loan.notify_committee_members(message=logged_comment.text,
                                                    subject="Application referred back to the agent assigned")

            if success:
                # Perform the necessary actions if emails are sent successfully
                loan.application.approved = False
                loan.application.save()
                loan.delete()
            else:
                # Return an error if emails fail
                return Response(
                    {"detail": "Failed to notify committee members. Loan not deleted."},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

        # Prepare serialized response
        response_data = {
            "detail": "Loan has been referred back to the agent.",
            "comment": {
                "id": logged_comment.id,
                "text": logged_comment.text,
                "created_by": logged_comment.created_by.email,
                "is_important": logged_comment.is_important,
                "application_id": logged_comment.application.id,
            }
        }

        return Response(response_data, status=status.HTTP_200_OK)

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

            # New boolean filters for committee approval fields
            OpenApiParameter(
                name='needs_committee_approval',
                description='Filter by needs committee approval status (true/false)',
                required=False,
                type=bool
            ),
            OpenApiParameter(
                name='is_committee_approved',
                description='Filter by committee approval status (true/false/null)',
                required=False,
                type=str  # Using string type to handle nullable boolean
            ),
        ]
    )
    @action(detail=False, methods=['get'], url_path='search-advanced-loans')
    def search_advanced_loans(self, request):
        """
        Search loans based on various model fields, supporting filtering and sorting.
        """
        queryset = self.queryset

        user = request.user
        country_filters = []

        # Determine the countries the user has access to
        if user.teams.filter(name='ie_team').exists():
            country_filters.append('IE')
        if user.teams.filter(name='uk_team').exists():
            country_filters.append('UK')

        # If no country filters were added, raise an error
        if not country_filters:
            raise PermissionDenied("You must be assigned to at least one team to access this resource.")

        # Filter applications based on the COUNTRY of the related user
        queryset = self.queryset.filter(application__user__country__in=country_filters)

        advancement_id = request.query_params.get('id')

        if advancement_id:
            queryset = queryset.filter(id=advancement_id)

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

            # Filter by needs_committee_approval (boolean)
        needs_committee_approval = request.query_params.get('needs_committee_approval')
        if needs_committee_approval is not None:
            queryset = queryset.filter(needs_committee_approval=(needs_committee_approval.lower() == 'true'))

        # Filter by is_committee_approved (nullable boolean)
        is_committee_approved = request.query_params.get('is_committee_approved')
        if is_committee_approved is not None:
            if is_committee_approved.lower() == 'null':
                queryset = queryset.filter(is_committee_approved__isnull=True)
            else:
                queryset = queryset.filter(is_committee_approved=(is_committee_approved.lower() == 'true'))

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
