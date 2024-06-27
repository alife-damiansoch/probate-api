"""
Test loan api
"""

import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from core.models import (Application, Deceased, Loan)

from loan.serializers import LoanSerializer

from decimal import Decimal


def get_detail_url(loan_id):
    """create the detail url"""
    return reverse('loans:loan-detail', args=[loan_id])


def create_application(user, **params):
    """create and return a new application object"""

    deceased = Deceased.objects.create(first_name="John", last_name="Doe")
    defaults = {
        'amount': 1000.00,
        'term': 12,

        'deceased': deceased,

    }
    defaults.update(params)
    application = Application.objects.create(user=user, **defaults)
    return application


def create_test_loan(user, application):
    # Now create a Loan
    loan = Loan.objects.create(
        application=application,
        amount_agreed=50000.00,
        fee_agreed=2000.00,
        term_agreed=12,
        approved_date=timezone.now(),
        is_settled=False,
        settled_date=None,
        approved_by=user,
        last_updated_by=user
    )
    return loan


class PublicLoanAPI(APITestCase):
    """Unauthenticated API tests"""

    def setUp(self):
        self.client = APIClient()
        self.LOANS_URL = reverse('loans:loan-list')

    def test_login_required(self):
        """test that login is required"""
        response = self.client.get(self.LOANS_URL)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_authenticated_non_staff_requests_returns_error(self):
        """Test that authentication is required for non-staff users"""
        user = get_user_model().objects.create_user(
            email='test@example.com',
            password='testpass'
        )
        self.client.force_authenticate(user=user)

        response = self.client.get(self.LOANS_URL)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class PrivateLoanAPI(APITestCase):
    """Test authenticated API tests"""

    def setUp(self):
        self.client = APIClient()
        self.LOANS_URL = reverse('loans:loan-list')
        self.user = get_user_model().objects.create_user(
            email='test@example.com',
            password='testpass',
            is_staff=True,
        )
        self.client.force_authenticate(user=self.user)

    def test_retrieve_loans(self):
        """test retrieving loans"""
        app1 = create_application(self.user)
        app2 = create_application(self.user)
        create_test_loan(self.user, app1)
        create_test_loan(self.user, app2)

        response = self.client.get(self.LOANS_URL)
        loans = Loan.objects.all().order_by('-id')
        serializer = LoanSerializer(loans, many=True)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, serializer.data)

    def test_loans_list_not_limited_to_authenticated_user(self):
        """Test retrieving loans for all users"""
        other_staff_user = get_user_model().objects.create_user(
            email='test1@example.com',
            password='testpass',
            is_staff=True,
        )
        app1 = create_application(self.user)
        app2 = create_application(other_staff_user)
        create_test_loan(self.user, app1)
        create_test_loan(other_staff_user, app2)

        response = self.client.get(self.LOANS_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        loans = Loan.objects.all().order_by('-id')
        serializer = LoanSerializer(loans, many=True)
        self.assertEqual(response.data, serializer.data)
