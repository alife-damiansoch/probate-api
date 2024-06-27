"""
Test loan_extension api
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from rest_framework import status
from rest_framework.test import APIClient, APITestCase

import user
from core.models import (Application, Deceased, Loan, LoanExtension)

from loan.serializers import (LoanExtensionSerializer, )


def get_detail_url(loan_extension_id):
    """create the detail url"""
    return reverse('loans:loan_extension-detail', args=[loan_extension_id])


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


class PublicLoanExtensionAPITestCase(APITestCase):
    """Unauthenticated Loan Extension API tests"""

    def setUp(self):
        self.client = APIClient()
        self.LOAN_EXTENSION_URL = reverse('loans:loan_extension-list')

    def test_login_required(self):
        """test that login is required"""
        response = self.client.get(self.LOAN_EXTENSION_URL)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_authenticated_non_staff_requests_returns_error(self):
        """Test that authentication is required for non-staff users"""
        other_user = get_user_model().objects.create_user(
            email='test@example.com',
            password='testpass'
        )
        self.client.force_authenticate(user=other_user)

        response = self.client.get(self.LOAN_EXTENSION_URL)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class PrivateLoanExtensionAPITestCase(APITestCase):
    """Authenticated Loan Extension API tests"""

    def setUp(self):
        self.client = APIClient()
        self.LOAN_EXTENSION_URL = reverse('loans:loan_extension-list')
        self.user = get_user_model().objects.create_user(
            email='test@example.com',
            password='testpass',
            is_staff=True,
        )
        self.client.force_authenticate(user=self.user)

    def test_retrieve_loan_extensions(self):
        """Test retrieving loan extensions"""
        app = create_application(user=self.user)
        loan = create_test_loan(self.user, application=app)
        ext1 = LoanExtension.objects.create(
            loan=loan,
            extension_term_months=3,
            extension_fee=1000,
            created_by=self.user,
            description="Test loan extension",
            created_date=timezone.now(),
        )
        ext2 = LoanExtension.objects.create(
            loan=loan,
            extension_term_months=2,
            extension_fee=2000,
            created_by=self.user,
            description="Test loan extension 2",
            created_date=timezone.now(),
        )
        response = self.client.get(self.LOAN_EXTENSION_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        loan_extensions = LoanExtension.objects.all().order_by('-id')
        serializer = LoanExtensionSerializer(loan_extensions, many=True)

        self.assertEqual(response.data, serializer.data)

        response_ids = [ext['id'] for ext in response.data]
        self.assertIn(ext1.id, response_ids)
        self.assertIn(ext2.id, response_ids)

    def test_retrieve_loan_extensions_by_id(self):
        """Test retrieving loan extensions by id"""
        app = create_application(user=self.user)
        loan = create_test_loan(self.user, application=app)
        ext1 = LoanExtension.objects.create(
            loan=loan,
            extension_term_months=3,
            extension_fee=1000,
            created_by=self.user,
            description="Test loan extension",
            created_date=timezone.now(),
        )
        detail_url = get_detail_url(ext1.id)
        response = self.client.get(detail_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        serializer = LoanExtensionSerializer(ext1)
        self.assertEqual(response.data, serializer.data)

    def test_retrieve_loan_extension_detail_created_by_other_user_works(self):
        """Test retrieving loan extension created by other user works"""
        other_user = get_user_model().objects.create_user(
            email='test2@example.com',
            password='testpass'
        )
        app = create_application(user=self.user)
        loan = create_test_loan(self.user, application=app)
        ext1 = LoanExtension.objects.create(
            loan=loan,
            extension_term_months=3,
            extension_fee=1000,
            created_by=other_user,
            description="Test loan extension",
            created_date=timezone.now(),
        )
        detail_url = get_detail_url(ext1.id)
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        serializer = LoanExtensionSerializer(ext1)
        self.assertEqual(response.data, serializer.data)

    def test_delete_loan_extension(self):
        """test deleting loan extension"""
        app = create_application(user=self.user)
        loan = create_test_loan(self.user, application=app)
        ext1 = LoanExtension.objects.create(
            loan=loan,
            extension_term_months=3,
            extension_fee=1000,
            created_by=self.user,
            description="Test loan extension",
            created_date=timezone.now(),
        )
        detail_url = get_detail_url(ext1.id)
        response = self.client.delete(detail_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(LoanExtension.objects.filter(id=ext1.id).exists())

    def test_update_loan_extension(self):
        """test updating loan extension"""
        app = create_application(user=self.user)
        loan = create_test_loan(self.user, application=app)
        ext1 = LoanExtension.objects.create(
            loan=loan,
            extension_term_months=3,
            extension_fee=1000,
            created_by=self.user,
            description="Test loan extension",
            created_date=timezone.now(),
        )
        detail_url = get_detail_url(ext1.id)
        response = self.client.patch(detail_url, {'extension_term_months': 6})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ext1.refresh_from_db()
        self.assertEqual(ext1.extension_term_months, 6)

    def test_updating_loan_in_loan_extension_returns_error(self):
        """test updating loan tor loan_extension returns error"""
        app = create_application(user=self.user)
        loan = create_test_loan(self.user, application=app)
        ext1 = LoanExtension.objects.create(
            loan=loan,
            extension_term_months=3,
            extension_fee=1000,
            created_by=self.user,
            description="Test loan extension",
            created_date=timezone.now(),
        )
        other_application = create_application(user=self.user)
        other_loan = create_test_loan(self.user, application=other_application)
        detail_url = get_detail_url(ext1.id)
        response = self.client.patch(detail_url, {'loan': other_loan.id})
        self.assertEqual(response.data['loan'], 'Cannot update loan for a transaction')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        ext1.refresh_from_db()
        self.assertEqual(ext1.loan, loan)
