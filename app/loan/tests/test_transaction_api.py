"""
Test transaction api
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from rest_framework import status
from rest_framework.test import APIClient, APITestCase

import user
from core.models import (Application, Deceased, Loan, Transaction)

from loan.serializers import (TransactionSerializer, )


def get_detail_url(loan_id):
    """create the detail url"""
    return reverse('loans:transaction-detail', args=[loan_id])


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


class PublicTransactionAPITestCase(APITestCase):
    """Unauthenticated Transaction API tests"""

    def setUp(self):
        self.client = APIClient()
        self.Transaction_URL = reverse('loans:transaction-list')

    def test_login_required(self):
        """test that login is required"""
        response = self.client.get(self.Transaction_URL)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_authenticated_non_staff_requests_returns_error(self):
        """Test that authentication is required for non-staff users"""
        other_user = get_user_model().objects.create_user(
            email='test@example.com',
            password='testpass'
        )
        self.client.force_authenticate(user=other_user)

        response = self.client.get(self.Transaction_URL)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class PrivateTransactionAPITestCase(APITestCase):
    """Authenticated Transaction API tests"""

    def setUp(self):
        self.LOANS_URL = reverse('loans:loan-list')
        self.user = get_user_model().objects.create_user(
            email='test@example.com',
            password='testpass',
            is_staff=True,
        )
        self.client.force_authenticate(user=self.user)
        self.Transaction_URL = reverse('loans:transaction-list')

    def test_retrieve_transactions(self):
        """Test retrieving a list of loans"""
        app = create_application(user=self.user)
        loan = create_test_loan(self.user, application=app)
        transaction1 = Transaction.objects.create(
            loan=loan,
            amount=1500.00,
            description="test description",
            created_by=self.user,
        )
        transaction2 = Transaction.objects.create(
            loan=loan,
            amount=1000.00,
            description="test description2",
            created_by=self.user,
        )
        response = self.client.get(self.Transaction_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        transactions = Transaction.objects.all().order_by('-id')
        serializer = TransactionSerializer(transactions, many=True)
        self.assertEqual(response.data, serializer.data)
        self.assertEqual(len(serializer.data), 2)

        response_ids = [trans['id'] for trans in response.data]
        self.assertIn(transaction1.id, response_ids)
        self.assertIn(transaction2.id, response_ids)

    def test_retrieve_transaction_detail(self):
        """test for retrieving a single transaction"""
        app = create_application(user=self.user)
        loan = create_test_loan(self.user, application=app)
        transaction1 = Transaction.objects.create(
            loan=loan,
            amount=1500.00,
            description="test description",
            created_by=self.user,
        )
        detail_url = get_detail_url(transaction1.id)
        response = self.client.get(detail_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        serializer = TransactionSerializer(transaction1)
        self.assertEqual(response.data, serializer.data)

    def test_retrieve_transaction_detail_created_by_other_user_works(self):
        """test for retrieving a single transaction"""
        other_user = get_user_model().objects.create_user(
            email='test2@example.com',
            password='testpass'
        )
        app = create_application(user=self.user)
        loan = create_test_loan(self.user, application=app)
        transaction1 = Transaction.objects.create(
            loan=loan,
            amount=1500.00,
            description="test description",
            created_by=other_user,
        )
        detail_url = get_detail_url(transaction1.id)
        response = self.client.get(detail_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        serializer = TransactionSerializer(transaction1)
        self.assertEqual(response.data, serializer.data)

    def test_create_transaction(self):
        """test for creating a new transaction"""
        app = create_application(user=self.user)
        loan = create_test_loan(self.user, application=app)
        payload = {
            "loan": loan.id,
            "amount": 1500.00,
            "description": "test description",
        }
        response = self.client.post(self.Transaction_URL, payload)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, f"error: {response.data}")
        self.assertEqual(response.data['loan'], loan.id)
        self.assertEqual(Decimal(response.data['amount']), Decimal(payload['amount']))
        self.assertEqual(response.data['description'], payload['description'])
        loan.refresh_from_db()
        self.assertEqual(Decimal(loan.current_balance),
                         Decimal(loan.amount_agreed) + Decimal(loan.fee_agreed) - Decimal(payload['amount']))
        self.assertEqual(Decimal(loan.amount_paid), Decimal(payload['amount']))
        self.assertEqual(response.data["created_by"], self.user.id)

    def test_delete_transaction(self):
        """test deleting transaction"""
        app = create_application(user=self.user)
        loan = create_test_loan(self.user, application=app)
        transaction1 = Transaction.objects.create(
            loan=loan,
            amount=1500.00,
            description="test description",
            created_by=self.user,
        )
        detail_url = get_detail_url(transaction1.id)
        response = self.client.delete(detail_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Transaction.objects.filter(id=transaction1.id).exists())

    def test_update_transaction(self):
        """test updating transaction"""
        app = create_application(user=self.user)
        loan = create_test_loan(self.user, application=app)
        transaction1 = Transaction.objects.create(
            loan=loan,
            amount=1500.00,
            description="test description",
            created_by=self.user,
        )
        detail_url = get_detail_url(transaction1.id)
        payload = {
            "amount": 1000.00,
            "description": "updated description",
        }
        response = self.client.patch(detail_url, payload)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        transaction1.refresh_from_db()
        self.assertEqual(transaction1.amount, payload['amount'])
        self.assertEqual(transaction1.description, payload['description'])

    def test_update_loan_tor_transaction_returns_error(self):
        """test updating loan tor transaction returns error"""
        app = create_application(user=self.user)
        loan = create_test_loan(self.user, application=app)
        transaction1 = Transaction.objects.create(
            loan=loan,
            amount=1500.00,
            description="test description",
            created_by=self.user,
        )
        other_application = create_application(user=self.user)
        other_loan = create_test_loan(self.user, application=other_application)

        payload = {
            "loan": other_loan.id,
        }
        response = self.client.patch(get_detail_url(transaction1.id), payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['loan'], 'Cannot update loan for a transaction')
