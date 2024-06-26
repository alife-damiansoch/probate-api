"""
Test expense api
"""
import json

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.test import TestCase
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from core.models import (Application, Deceased, Document, User, Event, Expense, )

from expense.serializers import ExpenseSerializer


def get_detail_url(expense_id):
    """create a detail url"""
    return reverse('expense:expense-detail', args=[expense_id])


def create_application(user, **params):
    """create and return a new application object"""

    deceased = Deceased.objects.create(first_name="John", last_name="Doe")
    defaults = {
        'amount': 1000.00,  # Default amount
        'term': 12,  # Default term
        'deceased': deceased,
    }
    defaults.update(params)
    application = Application.objects.create(user=user, **defaults)
    return application


class PublicExpenseAPITests(APITestCase):
    """Unauthenticated API tests"""

    def setUp(self):
        self.client = APIClient()
        self.EXPENSE_URL = reverse('expense:expense-list')

    def test_authentication_required(self):
        """Test that authentication is required"""
        response = self.client.get(self.EXPENSE_URL)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class PrivateExpenseAPITests(APITestCase):
    """Unauthenticated API tests"""

    def setUp(self):
        self.client = APIClient()
        self.EXPENSE_URL = reverse('expense:expense-list')
        self.user = get_user_model().objects.create_user(
            email='test@test.com',
            password='testpass'
        )
        self.client.force_authenticate(user=self.user)
        self.application = create_application(self.user)

    def test_retrieve_expenses_list(self):
        """Test retrieving a list of all expenses"""

        expense1 = Expense.objects.create(
            description="test expense",
            value=502.13,
            application=self.application,
        )
        expense2 = Expense.objects.create(
            description="test expense1",
            value=502.13,
            application=self.application,
        )

        response = self.client.get(self.EXPENSE_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        expenses = Expense.objects.all().order_by('-id')
        serializer = ExpenseSerializer(expenses, many=True)
        self.assertEqual(response.data, serializer.data)

        data = response.json()
        self.assertEqual(len(data), 2)

        # Ensure the response is sorted by id or any other criteria you expect
        data = sorted(data, key=lambda x: x['id'])
        expenses = [expense1, expense2]
        expenses.sort(key=lambda x: x.id)

        for i, expense in enumerate(expenses):
            self.assertEqual(data[i]['description'], expense.description)
            self.assertEqual(data[i]['value'], str(expense.value))
            self.assertEqual(data[i]['application'], expense.application.id)

    def test_create_expense_successful(self):
        """Test creating a new expense"""
        payload = {
            "application": self.application.id,
            "value": 502.13,
            "description": "test expense",
        }
        response = self.client.post(self.EXPENSE_URL, payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        expense = Expense.objects.get(id=response.data['id'])
        serializer = ExpenseSerializer(expense)
        self.assertEqual(response.data, serializer.data)

    def test_update_expense_successful(self):
        """Test updating an existing new expense"""
        expense = Expense.objects.create(
            description="test expense",
            value=502.13,
            application=self.application,
        )
        payload = {
            "value": 1000.00,
            "description": "updated expense",
        }
        response = self.client.patch(get_detail_url(expense.id), payload)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        expense.refresh_from_db()
        serializer = ExpenseSerializer(expense)
        self.assertEqual(response.data, serializer.data)
        self.assertEqual(expense.description, payload['description'])
        self.assertEqual(expense.value, payload['value'])

    def test_updating_application_in_existing_expense(self):
        """Test updating application in existing expense doesn't work"""
        expense = Expense.objects.create(
            description="test expense",
            value=502.13,
            application=self.application,
        )
        other_application = create_application(self.user)
        payload = {
            "application": other_application.id,
        }
        response = self.client.patch(get_detail_url(expense.id), payload)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotEqual(response.data['application'], other_application.id)
        self.assertEqual(response.data['application'], self.application.id)

    def test_delete_expense_successful(self):
        """Test deleting an existing expense"""
        expense = Expense.objects.create(
            description="test expense",
            value=502.13,
            application=self.application,
        )
        response = self.client.delete(get_detail_url(expense.id))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Expense.objects.filter(id=expense.id).exists())
