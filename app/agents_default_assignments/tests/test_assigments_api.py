"""
Test assignment API
"""
import json

from django.contrib.auth import get_user_model
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from core.models import Assignment


def create_user(**params):
    """Helper function to create and return a new user."""
    return get_user_model().objects.create_user(**params)


def create_assignment(staff_user, agency_user):
    """Helper function to create and return a new assignment."""
    return Assignment.objects.create(staff_user=staff_user, agency_user=agency_user)


def get_assignment_detail_url(assignment_id):
    """Return URL for a specific assignment detail."""
    return reverse('assignments:assignments-detail', kwargs={'pk': assignment_id})


class PublicAssignmentAPITestCase(APITestCase):
    """
    Test unauthenticated assignment API requests
    """

    def setUp(self):
        self.client = APIClient()
        self.ASSIGNMENT_LIST_URL = reverse('assignments:assignments-list')

    def test_login_required(self):
        """Test that login is required for assignments."""
        response = self.client.get(self.ASSIGNMENT_LIST_URL)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class PrivateAssignmentAPITestCase(APITestCase):
    """
    Test authenticated assignment API requests
    """

    def setUp(self):
        self.staff_user = create_user(
            email='staffuser@example.com',
            password='staffpassword',
            name='Staff User',
            is_staff=True
        )
        self.agency_user = create_user(
            email='agencyuser@example.com',
            password='agencypassword',
            name='Agency User',
            is_staff=False
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.staff_user)
        self.ASSIGNMENT_LIST_URL = reverse('assignments:assignments-list')

    def test_retrieve_assignments_list(self):
        """Test retrieving a list of assignments."""
        create_assignment(staff_user=self.staff_user, agency_user=self.agency_user)

        response = self.client.get(self.ASSIGNMENT_LIST_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(len(response.data) > 0)

    def test_retrieve_assignments_list_by_non_staff_user_forbidden(self):
        """Test retrieving a list of assignments."""
        create_assignment(staff_user=self.staff_user, agency_user=self.agency_user)

        non_staff_client = APIClient()
        non_staff_client.force_authenticate(user=self.agency_user)

        response = non_staff_client.get(self.ASSIGNMENT_LIST_URL)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_assignment_successful(self):
        """Test creating a new assignment."""
        payload = {
            'staff_user_id': self.staff_user.id,
            'agency_user_id': self.agency_user.id
        }
        response = self.client.post(self.ASSIGNMENT_LIST_URL, payload, format='json')

        if response.status_code != status.HTTP_201_CREATED:
            print(f"Response Status Code: {response.status_code}")
            print(f"Response Data: {response.data}")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        assignments = Assignment.objects.all()
        self.assertEqual(assignments.count(), 1)
        self.assertEqual(assignments[0].staff_user, self.staff_user)
        self.assertEqual(assignments[0].agency_user, self.agency_user)

    def test_retrieve_assignment_detail(self):
        """Test retrieving a specific assignment."""
        assignment = create_assignment(staff_user=self.staff_user, agency_user=self.agency_user)
        url = get_assignment_detail_url(assignment.id)
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['staff_user']['id'], self.staff_user.id)
        self.assertEqual(response.data['agency_user']['id'], self.agency_user.id)

    def test_update_assignment_successful(self):
        """Test updating an existing assignment."""
        assignment = create_assignment(staff_user=self.staff_user, agency_user=self.agency_user)

        # Create a new agency user to update the assignment
        new_agency_user = create_user(
            email='newagency@example.com',
            password='newagencypassword',
            name='New Agency User',
            is_staff=False
        )
        payload = {
            'staff_user_id': self.staff_user.id,
            'agency_user_id': new_agency_user.id
        }
        url = get_assignment_detail_url(assignment.id)
        response = self.client.put(url, payload, format='json')

        if response.status_code != status.HTTP_200_OK:
            print(f"Response Status Code: {response.status_code}")
            print(f"Response Data: {response.data}")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        assignment.refresh_from_db()
        self.assertEqual(assignment.agency_user, new_agency_user)

    def test_partial_update_assignment_successful(self):
        """Test partially updating an existing assignment."""
        assignment = create_assignment(staff_user=self.staff_user, agency_user=self.agency_user)

        payload = {'agency_user': {'id': self.agency_user.id}}
        url = get_assignment_detail_url(assignment.id)
        response = self.client.patch(url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        assignment.refresh_from_db()
        self.assertEqual(assignment.agency_user, self.agency_user)

    def test_delete_assignment_successful(self):
        """Test deleting an assignment."""
        assignment = create_assignment(staff_user=self.staff_user, agency_user=self.agency_user)
        url = get_assignment_detail_url(assignment.id)

        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Assignment.objects.count(), 0)

    def test_list_agencies_assigned_to_staff(self):
        """Test listing all agencies assigned to a specific staff user."""
        create_assignment(staff_user=self.staff_user, agency_user=self.agency_user)

        url = reverse('assignments:staff-assigned-agencies', args=[self.staff_user.id])
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(len(response.data) > 0)

    def test_list_staff_assigned_to_agency(self):
        """Test listing the staff user assigned to a specific agency."""
        create_assignment(staff_user=self.staff_user, agency_user=self.agency_user)

        url = reverse('assignments:agency-assigned-staff', args=[self.agency_user.id])
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(len(response.data) > 0)
