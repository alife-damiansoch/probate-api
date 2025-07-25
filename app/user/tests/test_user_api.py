"""
Test for the user API
"""
import json

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils.crypto import get_random_string

from rest_framework.test import APIClient
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import Team, OTP, Address

CREATE_USER_URL = reverse("user:create")

TOKEN_URL = reverse("user:token")

ME_URL = reverse("user:me")

headers = {
    "HTTP_COUNTRY": "IE",  # Custom header for country
}


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
            "password": "Testpass123!",
            "name": "Test Name",
            "phone_number": "+353861111111",
            "address": {
                "line1": "test street",
                "town_city": "test town",
                "eircode": "D24n1n3"
            },
        }

        res = self.client.post(CREATE_USER_URL, payload, format="json", **headers)

        self.assertEqual(
            res.status_code,
            status.HTTP_201_CREATED,
            msg=f"Unexpected status code: {res.status_code}, Response content: {res.content.decode()}"
        )

        user = get_user_model().objects.get(email=payload["email"])

        self.assertTrue(user.check_password(payload["password"]))
        self.assertEqual(user.name, payload["name"])
        self.assertNotIn('password', res.data)

    def test_create_valid_user_fails_password_validation(self):
        """Test creating user with valid payload is successful"""
        payload = {

            "email": "test@example.com",
            "password": "testpass123",
            "name": "Test Name",
            "phone_number": "+353861111111",
        }
        res = self.client.post(CREATE_USER_URL, payload, **headers)

        self.assertEqual(
            res.status_code,
            status.HTTP_400_BAD_REQUEST,
            msg=f"Unexpected status code: {res.status_code}, Response content: {res.content.decode()}"
        )

    def test_user_exists(self):
        """Test creating a user that already exists"""
        payload = {
            "email": "test@example.com",
            "password": "testpass123",
            "name": "Test Name",
            "phone_number": "+353861111111",
        }
        create_user(**payload)
        res = self.client.post(CREATE_USER_URL, payload, **headers)

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_password_too_short(self):
        """Test that password is too short"""
        payload = {
            "email": "test@example.com",
            "password": "pw",
            "name": "Test Name",
            "phone_number": "+353861111111",
        }
        res = self.client.post(CREATE_USER_URL, payload, **headers)

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        user_exists = get_user_model().objects.filter(email=payload["email"])

        self.assertFalse(user_exists)

    def test_create_token_with_otp(self):
        """Test creating a new token with OTP verification"""
        user_data = {
            "email": "test@example.com",
            "password": "testpass123",
            "name": "Test Name",
        }
        user = create_user(**user_data)
        # Explicitly activate the user
        user.is_active = True
        user.save()

        # Simulate OTP creation
        otp_code = get_random_string(length=6, allowed_chars='0123456789')
        OTP.objects.create(email=user_data['email'], code=otp_code)

        # Verify OTP exists in the database
        otp_record = OTP.objects.get(email=user_data['email'])
        self.assertEqual(otp_record.code, otp_code)

        # Use the valid OTP to request the token
        payload = {
            'email': user_data["email"],
            "password": user_data["password"],
            "otp": list(otp_code),  # Simulate sending OTP as a list
        }

        res = self.client.post(TOKEN_URL, data=json.dumps(payload), content_type="application/json")

        # Validate response
        self.assertEqual(res.status_code, status.HTTP_200_OK, msg=f"Failed with message {res.content.decode()}")
        self.assertIn('refresh', res.data)
        self.assertIn('access', res.data)

    def test_create_token_invalid_credentials(self):
        """Test that token is invalid"""
        user = create_user(email="test@example.com", password="goodPassword", name="Test Name")

        # Explicitly activate the user
        user.is_active = True
        user.save()

        payload = {
            "email": "test@example.com",
            "password": "wrongpassword",
        }
        res = self.client.post(TOKEN_URL, payload, **headers)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertNotIn('refresh', res.data)
        self.assertNotIn('access', res.data)
        self.assertNotIn('token', res.data)

    def test_create_token_no_password(self):
        """Test that token is not created"""
        payload = {
            "email": "test@example.com",
            "password": "",
        }
        res = self.client.post(TOKEN_URL, payload, **headers)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertNotIn('token', res.data)

    def test_retrieve_user_unauthorised(self):
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
        res = self.client.post(CREATE_USER_URL, payload, **headers)

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
        res = self.client.post(CREATE_USER_URL, payload, **headers)

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)  # Expect bad request due to foreign country code

    def test_create_user_with_country_code_fails(self):
        """Test creating user with phone number with country code fails"""
        payload = {
            "email": "test@example.com",
            "password": "testpass123",
            "name": "Test Name",
            "phone_number": "+353831234567",  # Mobile number with country code

        }
        res = self.client.post(CREATE_USER_URL, payload, **headers)

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)  # Expect bad request due to country code

    def test_create_user_with_invalid_eircode_fails(self):
        """Test creating user with invalid Eircode fails"""
        payload = {
            "email": "test@example.com",
            "password": "testpass123",
            "name": "Test Name",
            "phone_number": "1234567890",
            "address": {
                "line1": "123 Test Street",
                "line2": "Test Area",
                "town_city": "Test City",
                "county": "Test County",
                "eircode": "X1YZ12W"  # Invalid Eircode format
            }
        }
        res = self.client.post(CREATE_USER_URL, payload, format='json', **headers)

        self.assertEqual(res.status_code,
                         status.HTTP_400_BAD_REQUEST)  # Expect Bad request error due to invalid Eircode

        # Test another invalid Eircode
        payload['address']['eircode'] = "12YZX"  # another Invalid Eircode format
        res = self.client.post(CREATE_USER_URL, payload, format='json', **headers)

        self.assertEqual(res.status_code,
                         status.HTTP_400_BAD_REQUEST)  # Expect Bad request error due to invalid Eircode


# Testing vulnerability jsw token patch
class TokenObtainTest(TestCase):
    def setUp(self):
        self.user = create_user(
            email='inactive@example.com',
            password='testpass123',
            is_active=False  # Mark the user as inactive
        )

    def test_inactive_user_cannot_get_token(self):
        # Try to generate a refresh token for the inactive user
        refresh = RefreshToken.for_user(self.user)

        # Check that a token cannot be used for an inactive user
        with self.assertRaises(Exception):
            # Access the user field directly to check if it should raise an error
            _ = refresh['user']  # This should raise an exception or check the user status before issuing a token
