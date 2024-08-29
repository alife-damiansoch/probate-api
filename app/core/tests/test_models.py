"""
Tests for models
"""

from decimal import Decimal

from dateutil.relativedelta import relativedelta
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone

from core import models

from unittest.mock import patch

from uuid import uuid4

from os.path import join

from core.models import AssignedSolicitor


class TestModels(TestCase):
    """Tests for models"""

    # region <Tests fo User model>
    def test_create_user_with_email_successful(self):
        """Test creating a new user with an email is successful"""
        email = 'testemail@example.com'
        password = 'testpass123'
        user = get_user_model().objects.create_user(
            email=email,
            password=password,
            name='testuser'
        )

        self.assertEqual(user.email, email)
        self.assertTrue(user.check_password(password))

    def test_new_user_email_normalized(self):
        """Test the email for a new user is normalized"""
        sample_emails = [
            ["test1@EXAMPLE.com", "test1@example.com"],
            ["Test2@Example.COM", "Test2@example.com"],
            ["TEST3@EXAMPLE.com", "TEST3@example.com"],
            ["test4@example.COM", "test4@example.com"],
        ]
        for email, expected in sample_emails:
            user = get_user_model().objects.create_user(email, "sample123")
            self.assertEqual(user.email, expected)

    def test_new_user_without_email_raises_error(self):
        """Test creating user with no email is raised error"""
        with self.assertRaises(ValueError):
            get_user_model().objects.create_user("", "sample123")

    def test_create_superuser(self):
        """Test creating a superuser"""
        user = get_user_model().objects.create_superuser(
            "test@example.com", "testpass123"
        )
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_staff)

    # endregion


class ApplicationModelTest(TestCase):

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email='test@email.com',
            password='testpass123'
        )

        self.deceased = models.Deceased.objects.create(
            first_name='Deceased',
            last_name='Test'
        )

        self.dispute = models.Dispute.objects.create(
            details='Test Dispute'
        )

    def test_create_application(self):
        application = models.Application.objects.create(
            amount=100.0,
            term=12,
            user=self.user,
            deceased=self.deceased,
            dispute=self.dispute,
            approved=False
        )

        self.assertEqual(models.Application.objects.count(), 1)
        self.assertEqual(models.Application.objects.get().amount,
                         application.amount)
        self.assertEqual(models.Application.objects.get().term, application.term)
        self.assertEqual(models.Application.objects.get().user, self.user)
        self.assertEqual(models.Application.objects.get().deceased, self.deceased)
        self.assertEqual(models.Application.objects.get().dispute, self.dispute)
        self.assertEqual(models.Application.objects.get().approved, application.approved)

    @patch('core.models.uuid.uuid4')
    def test_solicitor_application_file_name_uuid(self, mock_uuid):
        """Test generating file path"""
        uuid = 'test-uuid'
        mock_uuid.return_value = uuid
        file_path = models.get_application_document_file_path(None, 'example.pdf')

        expected_path = join('uploads', 'application', f'{uuid}.pdf')
        self.assertEqual(file_path, expected_path)

    def test_deceased_deleted_when_application_deleted(self):
        """Test that the Deceased instance is deleted when the Application is deleted."""
        application = models.Application.objects.create(
            amount=100.0,
            term=12,
            user=self.user,
            deceased=self.deceased,
            dispute=self.dispute,
            approved=False
        )

        # Delete the application
        application.delete()

        # Check that the Deceased instance is also deleted
        deceased_exists = models.Deceased.objects.filter(id=self.deceased.id).exists()
        self.assertFalse(deceased_exists, "Deceased instance was not deleted when the Application was deleted.")

    def test_dispute_deleted_when_application_deleted(self):
        """Test that the Dispute instance is deleted when the Application is deleted."""
        application = models.Application.objects.create(
            amount=100.0,
            term=12,
            user=self.user,
            deceased=self.deceased,
            dispute=self.dispute,
            approved=False
        )

        # Delete the application
        application.delete()

        # Check that the Dispute instance is also deleted
        dispute_exists = models.Dispute.objects.filter(id=self.dispute.id).exists()
        self.assertFalse(dispute_exists, "Dispute instance was not deleted when the Application was deleted.")


class EventModelTest(TestCase):

    def setUp(self):
        self.request_id = uuid4()
        models.Event.objects.create(
            request_id=self.request_id,
            user='test_user',
            method='POST',
            path='/test_path',
            body='{}',
            is_notification=True,
            is_staff=True,
        )

    def test_event_created(self):
        event = models.Event.objects.get(request_id=self.request_id)
        self.assertEqual(event.user, 'test_user')


class CommentModelTest(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email='test@example.com',
            password='testpass123'
        )

        self.deceased = models.Deceased.objects.create(
            first_name='Deceased',
            last_name='Test'
        )

        self.application = models.Application.objects.create(
            amount=100.0,
            term=12,
            user=self.user,
            deceased=self.deceased,
            approved=False
        )

    def test_create_comment(self):
        comment = models.Comment.objects.create(
            application=self.application,
            created_by=self.user,
            text='Test comment'
        )

        comments = models.Comment.objects.all()

        self.assertEqual(comments.count(), 1)
        comment = comments[0]
        self.assertEqual(comment.application, self.application)
        self.assertEqual(comment.created_by, self.user)
        self.assertEqual(comment.text, comment.text)
        self.assertEqual(comment.updated_by, None)


class ExpenseModelTest(TestCase):
    """Test for Expense Model"""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email='test@example.com',
            password='testpass123'
        )

        self.deceased = models.Deceased.objects.create(
            first_name='Deceased',
            last_name='Test'
        )

        self.application = models.Application.objects.create(
            amount=100.0,
            term=12,
            user=self.user,
            deceased=self.deceased,
            approved=False
        )

    def test_create_expense(self):
        """Test creating an Expense Model"""
        exp = models.Expense.objects.create(
            application=self.application,
            value=50.0,
            description='Test expense'
        )

        expenses = models.Expense.objects.all()
        self.assertEqual(expenses.count(), 1)
        expense = expenses[0]
        self.assertEqual(expense.value, exp.value)
        self.assertEqual(expense.description, exp.description)
        self.assertEqual(expense.application, self.application)


class LoanModelTests(TestCase):

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email='testuser@example.com',
            password='testpass123'
        )
        self.application = models.Application.objects.create(
            amount=100000,
            term=12,
            user=self.user,
            approved=False,
        )

    def test_create_loan(self):
        """Test creating a Loan Model"""
        loan1 = models.Loan.objects.create(
            application=self.application,
            amount_agreed=500000,
            fee_agreed=5000,
            term_agreed=12,
            approved_date=timezone.now().date(),  # Ensure approved_date is a date object
        )

        loans = models.Loan.objects.all()
        self.assertEqual(loans.count(), 1)
        loan = loans[0]
        self.assertEqual(loan.application, self.application)
        self.assertEqual(loan.amount_agreed, loan1.amount_agreed)
        self.assertEqual(loan.fee_agreed, loan1.fee_agreed)
        self.assertEqual(loan.term_agreed, loan1.term_agreed)

        # Assert current_balance and amount_paid
        self.assertEqual(loan.current_balance, loan1.current_balance)
        self.assertEqual(loan.amount_paid, loan1.amount_paid)

        # Expected maturity date as a date object
        expected_maturity_date = loan1.approved_date + relativedelta(months=loan1.term_agreed)
        self.assertEqual(loan.maturity_date, expected_maturity_date)

    def test_transactions_and_extensions_affect_balance_and_maturity(self):
        """Test that transactions and extensions affect the loan balance and maturity date correctly"""
        transactions = (100000, 150000,)
        fees = (1000, 5000)
        loan = models.Loan.objects.create(
            application=self.application,
            amount_agreed=500000,
            fee_agreed=fees[1],
            term_agreed=12,
            approved_date=timezone.now().date(),  # Ensure approved_date is a date object
        )

        models.Transaction.objects.create(loan=loan, amount=transactions[0], created_by=self.user,
                                          transaction_date=timezone.now())
        models.Transaction.objects.create(loan=loan, amount=transactions[1], created_by=self.user,
                                          transaction_date=timezone.now())
        models.LoanExtension.objects.create(loan=loan, extension_term_months=6, extension_fee=fees[0],
                                            created_by=self.user,
                                            created_date=timezone.now())

        loan.refresh_from_db()
        self.assertEqual(loan.current_balance,
                         loan.amount_agreed + sum(fees) - sum(
                             transactions))
        self.assertEqual(loan.amount_paid, Decimal(sum(transactions)))

        # Expected maturity date with extension as a date object
        expected_maturity_date = loan.approved_date + relativedelta(months=loan.term_agreed + 6)
        self.assertEqual(loan.maturity_date, expected_maturity_date)

    def test_creating_loan_updates_application_connected_to_approved(self):
        """Test when creating a Loan Model application connected is marked as approved"""
        loan1 = models.Loan.objects.create(
            application=self.application,
            amount_agreed=500000,
            fee_agreed=5000,
            term_agreed=12,
            approved_date=timezone.now().date(),  # Ensure approved_date is a date object
        )
        self.application.refresh_from_db()
        self.assertTrue(self.application.approved)


class AssignedSolicitorModelTest(TestCase):

    def setUp(self):
        # Create a test user
        self.user = get_user_model().objects.create_user(
            email='solicitor_user@test.com',
            password='testpass123'
        )

    def test_create_assigned_solicitor(self):
        # Create an AssignedSolicitor instance
        solicitor = AssignedSolicitor.objects.create(
            user=self.user,
            title='Mr.',
            first_name='John',
            last_name='Doe',
            own_email='john.doe@example.com',
            own_phone_number='1234567890'
        )

        # Verify that an AssignedSolicitor instance was created
        self.assertEqual(AssignedSolicitor.objects.count(), 1)

        # Retrieve the created instance
        created_solicitor = AssignedSolicitor.objects.get()

        # Verify that the created solicitor's fields match the input
        self.assertEqual(created_solicitor.user, self.user)
        self.assertEqual(created_solicitor.title, 'Mr.')
        self.assertEqual(created_solicitor.first_name, 'John')
        self.assertEqual(created_solicitor.last_name, 'Doe')
        self.assertEqual(created_solicitor.own_email, 'john.doe@example.com')
        self.assertEqual(created_solicitor.own_phone_number, '1234567890')

    def test_create_assigned_solicitor_with_optional_fields(self):
        # Create an AssignedSolicitor instance with optional fields set to None
        solicitor = AssignedSolicitor.objects.create(
            user=self.user,
            title='Ms.',
            first_name='Jane',
            last_name='Doe',
            own_email=None,  # Optional field set to None
            own_phone_number=None  # Optional field set to None
        )

        # Verify that an AssignedSolicitor instance was created
        self.assertEqual(AssignedSolicitor.objects.count(), 1)

        # Retrieve the created instance
        created_solicitor = AssignedSolicitor.objects.get()

        # Verify that the created solicitor's fields match the input
        self.assertEqual(created_solicitor.user, self.user)
        self.assertEqual(created_solicitor.title, 'Ms.')
        self.assertEqual(created_solicitor.first_name, 'Jane')
        self.assertEqual(created_solicitor.last_name, 'Doe')
        self.assertIsNone(created_solicitor.own_email)  # Ensure optional field is None
        self.assertIsNone(created_solicitor.own_phone_number)  # Ensure optional field is None
