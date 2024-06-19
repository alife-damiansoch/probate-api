"""
Tests for models
"""
from datetime import datetime
import random
from decimal import Decimal

from django.test import TestCase
from django.contrib.auth import get_user_model

from core import models


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
        self.assertEqual(models.Application.objects.get().amount, 100.0)
        self.assertEqual(models.Application.objects.get().term, 12)
        self.assertEqual(models.Application.objects.get().user, self.user)
        self.assertEqual(models.Application.objects.get().deceased, self.deceased)
        self.assertEqual(models.Application.objects.get().dispute, self.dispute)
        self.assertEqual(models.Application.objects.get().approved, False)
