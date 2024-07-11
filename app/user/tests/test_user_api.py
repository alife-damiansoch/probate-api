"""
Test for the user API
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse

from rest_framework.test import APIClient
from rest_framework import status

from core.models import Team

CREATE_USER_URL = reverse("user:create")

TOKEN_URL = reverse("user:token")

ME_URL = reverse("user:me")


def create_user(**params):
    """Create and return new user"""
    return get_user_model().objects.create_user(**params)


class PublicCustomUserTests(TestCase):
    """Test the user API (public)"""

    def setUp(self):
        self.client = APIClient()

    def test_create_valid_user_success(self):
        """Test creating user with valid payload is successful"""
        payload = {

            "email": "test@example.com",
            "password": "testpass123",
            "name": "Test Name",
        }
        res = self.client.post(CREATE_USER_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        user = get_user_model().objects.get(email=payload["email"])

        self.assertTrue(user.check_password(payload["password"]))
        self.assertEqual(user.name, payload["name"])
        self.assertNotIn('password', res.data)

    def test_user_exists(self):
        """Test creating a user that already exists"""
        payload = {
            "email": "test@example.com",
            "password": "testpass123",
            "name": "Test Name",
        }
        create_user(**payload)
        res = self.client.post(CREATE_USER_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_password_too_short(self):
        """Test that password is too short"""
        payload = {
            "email": "test@example.com",
            "password": "pw",
            "name": "Test Name",
        }
        res = self.client.post(CREATE_USER_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        user_exists = get_user_model().objects.filter(email=payload["email"])

        self.assertFalse(user_exists)

    def create_token(self):
        """Test creating a new token"""
        user_data = {
            "email": "test@example.com",
            "password": "testpass123",
            "name": "Test Name",
        }
        user = create_user(**user_data)
        payload = {
            'email': user_data["email"],
            "password": user_data["password"],
            "name": user_data["name"],
        }
        res = self.client.post(TOKEN_URL, payload)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn('token', res.data)

    def test_create_token_invalid_credentials(self):
        """Test that token is invalid"""
        create_user(email="test@example.com", password="goodPassword", name="Test Name")
        payload = {
            "email": "test@example.com",
            "password": "wrongpassword",
        }
        res = self.client.post(TOKEN_URL, payload)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertNotIn('token', res.data)

    def test_create_token_no_password(self):
        """Test that token is not created"""
        payload = {
            "email": "test@example.com",
            "password": "",
        }
        res = self.client.post(TOKEN_URL, payload)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertNotIn('token', res.data)

    def retrieve_user_unauthorised(self, token):
        """Test authentication is required for users"""
        res = self.client.get(ME_URL)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_user_with_invalid_phone_number_fails(self):
        """Test creating user with invalid phone number fails"""
        payload = {

            "email": "test@example.com",
            "password": "testpass123",
            "name": "Test Name",
            "phone_number": "1234567890",  # Invalid number format
        }
        res = self.client.post(CREATE_USER_URL, payload)

        self.assertEqual(res.status_code,
                         status.HTTP_400_BAD_REQUEST)  # Expect Bad request error due to invalid phone number

    def test_create_user_with_foreign_country_code_fails(self):
        """Test creating user with phone number of foreign country code fails"""
        payload = {
            "email": "test@example.com",
            "password": "testpass123",
            "name": "Test Name",
            "phone_number": "+12021234567",  # US number format
        }
        res = self.client.post(CREATE_USER_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)  # Expect bad request due to foreign country code

    def test_create_user_with_country_code_fails(self):
        """Test creating user with phone number with country code fails"""
        payload = {
            "email": "test@example.com",
            "password": "testpass123",
            "name": "Test Name",
            "phone_number": "+353831234567",  # Mobile number with country code
        }
        res = self.client.post(CREATE_USER_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)  # Expect bad request due to country code
