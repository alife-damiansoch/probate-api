import random
import uuid

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from core.models import Solicitor
from assigned_solicitor.serializers import AssignedSolicitorSerializer


def create_assigned_solicitor(user, **params):
    """Helper function to create and return a new AssignedSolicitor"""
    defaults = {
        'title': 'Mr.',
        'first_name': 'John',
        'last_name': 'Doe',
        'own_email': f'john.doe_{random.randint(0, 1000)}@example.com',
        'own_phone_number': '1234567890',
    }
    defaults.update(params)
    return Solicitor.objects.create(user=user, **defaults)


def get_detail_url(solicitor_id):
    """Create and return a detail URL for an assigned solicitor"""
    return reverse('assigned_solicitor:assigned_solicitor-detail', args=[solicitor_id])


class AssignedSolicitorModelTest(APITestCase):
    """Test suite for the AssignedSolicitor model and API"""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email='user@example.com',
            password='testpass123'
        )
        self.staff_user = get_user_model().objects.create_user(
            email='staff@example.com',
            password='testpass123',
            is_staff=True
        )
        self.client.force_authenticate(self.user)
        self.ASSIGNED_SOLICITORS_URL = reverse('assigned_solicitor:assigned_solicitor-list')

    def test_retrieve_assigned_solicitors_non_staff(self):
        """Test retrieving only assigned solicitors for non-staff users"""

        # Create solicitors associated with the authenticated user
        solicitor1 = create_assigned_solicitor(user=self.user)
        solicitor2 = create_assigned_solicitor(user=self.user)

        # Create solicitors associated with other users
        other_user = get_user_model().objects.create_user(
            email='other@example.com',
            password='testpass123'
        )
        create_assigned_solicitor(user=other_user)
        create_assigned_solicitor(user=self.staff_user)

        # Retrieve solicitors using the authenticated client
        response = self.client.get(self.ASSIGNED_SOLICITORS_URL)

        # Filter the queryset to match expected results
        solicitors = Solicitor.objects.filter(user=self.user).order_by('-id')
        serializer = AssignedSolicitorSerializer(solicitors, many=True)

        # Check the response
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, serializer.data)

    def test_retrieve_assigned_solicitors_staff(self):
        """Test retrieving all assigned solicitors for staff users"""

        self.client.force_authenticate(self.staff_user)

        # Create solicitors associated with different users
        create_assigned_solicitor(user=self.user)
        create_assigned_solicitor(user=self.staff_user)
        create_assigned_solicitor(user=self.user)
        create_assigned_solicitor(user=self.staff_user)

        # Retrieve solicitors using the authenticated client
        response = self.client.get(self.ASSIGNED_SOLICITORS_URL)

        # Filter the queryset to match expected results
        solicitors = Solicitor.objects.all().order_by('-id')
        serializer = AssignedSolicitorSerializer(solicitors, many=True)

        # Check the response
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, serializer.data)

    def test_create_assigned_solicitor_staff_forbidden(self):
        """Test that creating an assigned solicitor is forbidden for staff users"""
        self.client.force_authenticate(self.staff_user)
        payload = {
            'title': 'Ms.',
            'first_name': 'Emily',
            'last_name': 'Doe',
            'own_email': 'emily.doe@example.com',
            'own_phone_number': '+353868406699'
        }
        response = self.client.post(self.ASSIGNED_SOLICITORS_URL, payload)

        # Staff users are not allowed to create solicitors
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_assigned_solicitor_non_staff(self):
        """Test creating an assigned solicitor for non-staff user"""
        payload = {
            'title': 'Ms.',
            'first_name': 'Emily',
            'last_name': 'Doe',
            'own_email': 'emily.doe@example.com',
            'own_phone_number': '+353868406699'
        }
        response = self.client.post(self.ASSIGNED_SOLICITORS_URL, payload)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        solicitor = Solicitor.objects.get(id=response.data['id'])
        self.assertEqual(solicitor.user, self.user)
        self.assertEqual(solicitor.title, payload['title'])
        self.assertEqual(solicitor.first_name, payload['first_name'])
        self.assertEqual(solicitor.last_name, payload['last_name'])
        self.assertEqual(solicitor.own_email, payload['own_email'])
        self.assertEqual(solicitor.own_phone_number, payload['own_phone_number'])

    def test_get_assigned_solicitor_by_id_staff(self):
        """Test retrieving an assigned solicitor by ID for staff user"""
        solicitor = create_assigned_solicitor(user=self.user)

        self.client.force_authenticate(self.staff_user)
        url = get_detail_url(solicitor.id)
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        serializer = AssignedSolicitorSerializer(solicitor)
        self.assertEqual(response.data, serializer.data)

    def test_get_assigned_solicitor_by_id_non_staff(self):
        """Test retrieving an assigned solicitor by ID for non-staff user"""
        solicitor = create_assigned_solicitor(user=self.user)

        url = get_detail_url(solicitor.id)
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        serializer = AssignedSolicitorSerializer(solicitor)
        self.assertEqual(response.data, serializer.data)

    def test_get_assigned_solicitor_by_id_staff_different_user(self):
        """Test retrieving an assigned solicitor by ID for staff user when solicitor belongs to a different user"""
        other_user = get_user_model().objects.create_user(
            email='other@example.com',
            password='testpass123'
        )
        solicitor = create_assigned_solicitor(user=other_user)

        self.client.force_authenticate(self.staff_user)
        url = get_detail_url(solicitor.id)
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        serializer = AssignedSolicitorSerializer(solicitor)
        self.assertEqual(response.data, serializer.data)

    def test_get_assigned_solicitor_by_id_non_staff_different_user(self):
        """Test retrieving an assigned solicitor by ID for non-staff user when solicitor belongs to a different user"""
        other_user = get_user_model().objects.create_user(
            email='other@example.com',
            password='testpass123'
        )
        solicitor = create_assigned_solicitor(user=other_user)

        url = get_detail_url(solicitor.id)
        response = self.client.get(url)

        # Expect 404 Not Found because non-staff users cannot access others' data
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        # Existing tests...

    def test_partial_update_assigned_solicitor(self):
        """Test partially updating an assigned solicitor"""
        solicitor = create_assigned_solicitor(user=self.user)

        payload = {'first_name': 'Jane'}
        url = get_detail_url(solicitor.id)
        response = self.client.patch(url, payload)

        solicitor.refresh_from_db()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(solicitor.first_name, payload['first_name'])
        self.assertEqual(solicitor.user, self.user)

    def test_full_update_assigned_solicitor(self):
        """Test fully updating an assigned solicitor"""
        solicitor = create_assigned_solicitor(user=self.user)

        payload = {
            'title': 'Mrs.',
            'first_name': 'Jane',
            'last_name': 'Smith',
            'own_email': 'jane.smith@example.com',
            'own_phone_number': '0987654321'
        }
        url = get_detail_url(solicitor.id)
        response = self.client.put(url, payload)

        solicitor.refresh_from_db()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(solicitor.title, payload['title'])
        self.assertEqual(solicitor.first_name, payload['first_name'])
        self.assertEqual(solicitor.last_name, payload['last_name'])
        self.assertEqual(solicitor.own_email, payload['own_email'])
        self.assertEqual(solicitor.own_phone_number, payload['own_phone_number'])
        self.assertEqual(solicitor.user, self.user)

    def test_delete_assigned_solicitor(self):
        """Test deleting an assigned solicitor"""
        solicitor = create_assigned_solicitor(user=self.user)

        url = get_detail_url(solicitor.id)
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Solicitor.objects.filter(id=solicitor.id).exists())

    def test_partial_update_assigned_solicitor_other_user_forbidden(self):
        """Test that partial update of another user's assigned solicitor is forbidden"""
        other_user = get_user_model().objects.create_user(
            email='other@example.com',
            password='testpass123'
        )
        solicitor = create_assigned_solicitor(user=other_user)

        payload = {'first_name': 'Jane'}
        url = get_detail_url(solicitor.id)
        response = self.client.patch(url, payload)

        # Expect 404 Not Found because non-staff users cannot access others' data
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_assigned_solicitor_other_user_forbidden(self):
        """Test that delete of another user's assigned solicitor is forbidden"""
        other_user = get_user_model().objects.create_user(
            email='other@example.com',
            password='testpass123'
        )
        solicitor = create_assigned_solicitor(user=other_user)

        url = get_detail_url(solicitor.id)
        response = self.client.delete(url)

        # Expect 404 Not Found because non-staff users cannot access others' data
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
