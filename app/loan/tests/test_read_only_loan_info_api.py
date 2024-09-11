from agents_loan.tests.test_agents_application_api import create_application
from core.models import Loan, Application
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase, APIClient
from django.contrib.auth import get_user_model

from loan.serializers import LoanSerializer
from loan.tests.test_loan_api import create_test_loan


class ReadOnlyLoanAPITest(APITestCase):
    """Tests for the read-only loan by application ID endpoint"""

    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            email='user@example.com',
            password='testpass'
        )
        self.staff_user = get_user_model().objects.create_user(
            email='staff@example.com',
            password='testpass',
            is_staff=True
        )
        self.application = create_application(user=self.user)
        self.loan = create_test_loan(self.user, self.application)
        self.READONLY_LOAN_URL = reverse('loans:loan_by_application', args=[self.application.id])

    def test_read_only_access_non_staff_own_application(self):
        """Test non-staff user can access the loan linked to their own application"""
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.READONLY_LOAN_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        loan = Loan.objects.get(application=self.application)
        serializer = LoanSerializer(loan)
        self.assertEqual(response.data, serializer.data)

    def test_read_only_access_non_staff_other_user_application(self):
        """Test non-staff user cannot access loan linked to another user's application"""
        other_user = get_user_model().objects.create_user(
            email='other@example.com',
            password='testpass'
        )
        self.client.force_authenticate(user=other_user)
        response = self.client.get(self.READONLY_LOAN_URL)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_read_only_access_staff_user(self):
        """Test staff user can access any loan"""
        self.client.force_authenticate(user=self.staff_user)
        response = self.client.get(self.READONLY_LOAN_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        loan = Loan.objects.get(application=self.application)
        serializer = LoanSerializer(loan)
        self.assertEqual(response.data, serializer.data)

    def test_read_only_access_unauthenticated_user(self):
        """Test unauthenticated user cannot access the endpoint"""
        response = self.client.get(self.READONLY_LOAN_URL)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
