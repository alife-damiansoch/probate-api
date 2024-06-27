from drf_spectacular.utils import extend_schema_view, extend_schema
from rest_framework import viewsets, mixins
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from core.models import Expense
from expense.serializers import ExpenseSerializer


@extend_schema_view(
    list=extend_schema(
        summary='Retrieve all expenses',
        description='Returns  all expenses.',
        tags=['expenses'],
    ),
    retrieve=extend_schema(
        summary='Retrieve an expense ',
        description='Returns detailed information about an expenses.',
        tags=['expenses'],
    ),

    create=extend_schema(
        summary='Create an new expense',
        description='Creates a new expense and returns information about the created expense.',
        tags=['expenses']
    ),

    update=extend_schema(
        summary='Update an expense ',
        description='Updates an existing expense and returns information about the updated expense.',
        tags=['expenses']
    ),

    partial_update=extend_schema(
        summary='Partially update an expense ',
        description='Partially updates an existing expense and returns information about the updated expense.',
        tags=['expenses']
    ),

    destroy=extend_schema(
        summary='Delete an expense ',
        description='Deletes an existing expense and does not return any content.',
        tags=['expenses']
    )
)
class ExpenseViewSet(mixins.ListModelMixin,
                     mixins.CreateModelMixin,
                     mixins.UpdateModelMixin,
                     mixins.DestroyModelMixin,
                     viewsets.GenericViewSet):
    """ViewSet for viewing Expense objects."""
    queryset = Expense.objects.all()
    serializer_class = ExpenseSerializer
    authentication_classes = (TokenAuthentication,)
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        return self.queryset.order_by('-id')
