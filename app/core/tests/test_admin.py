"""
Test for the Django admin modifications.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.test import Client


class AdminTestCase(TestCase):
    """Tests for the Django admin modifications."""

    def setUp(self):
        """Create a test user and client."""

        self.client = Client()
        # creating superuser that we can use for the tests
        self.admin_user = get_user_model().objects.create_superuser(
            email='admin@example.com',
            password='testpass123',
        )
        self.client.force_login(self.admin_user)
        # creating regular user that we can use for the tests
        self.user = get_user_model().objects.create_user(
            email='user@example.com',
            password='testpass123',
            name='testuser',
        )

    def test_users_list(self):
        """Test that the users list works."""
        url = reverse('admin:core_user_changelist')
        res = self.client.get(url)

        self.assertContains(res, self.user.name)
        self.assertContains(res, self.user.email)

    def test_edit_user_page(self):
        """Test the edit user page works"""
        url = reverse("admin:core_user_change", args=[self.user.id])
        res = self.client.get(url)

        self.assertEqual(res.status_code, 200)

    def test_create_user_page(self):
        """Test the create user page works"""
        url = reverse("admin:core_user_add")
        res = self.client.get(url)

        self.assertEqual(res.status_code, 200)
