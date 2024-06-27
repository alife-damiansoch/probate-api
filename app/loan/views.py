"""
viewsets for Loan api
"""

from rest_framework import (viewsets, )
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from .permissions import IsStaff

from core.models import Loan
from loan import serializers


class LoanViewSet(viewsets.ModelViewSet):
    """View for manage Loan Apis"""
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsStaff]
    queryset = Loan.objects.all()
    serializer_class = serializers.LoanSerializer

    def get_queryset(self):
        return self.queryset.order_by('-id')
