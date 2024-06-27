"""
viewsets for Loan api
"""

from rest_framework import (viewsets, )
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from .permissions import IsStaff

from core.models import Loan, Transaction, LoanExtension
from loan import serializers


class TransactionViewSet(viewsets.ModelViewSet):
    """VIewset for Transaction Viewset"""
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsStaff]
    queryset = Loan.objects.all()
    serializer_class = serializers.TransactionSerializer

    def get_queryset(self):
        return Transaction.objects.all().order_by('-id')

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class LoanExtensionViewSet(viewsets.ModelViewSet):
    """viewset for LoanExtension APIs"""
    queryset = LoanExtension.objects.all()
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsStaff]
    serializer_class = serializers.LoanExtensionSerializer

    def get_queryset(self):
        return LoanExtension.objects.all().order_by('-id')

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class LoanViewSet(viewsets.ModelViewSet):
    """View for manage Loan Apis"""
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsStaff]
    queryset = Loan.objects.all()
    serializer_class = serializers.LoanSerializer

    def get_queryset(self):
        return self.queryset.order_by('-id')
