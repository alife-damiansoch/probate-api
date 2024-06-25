"""
Test solicitors_application api
"""
import json

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.test import TestCase
from django.urls import reverse

from rest_framework import status
from rest_framework.status import HTTP_403_FORBIDDEN, HTTP_204_NO_CONTENT, HTTP_400_BAD_REQUEST
from rest_framework.test import APIClient, APITestCase

from core.models import (Event, Application, Deceased, )
from event.serializers import EventSerializer

from solicitors_loan import serializers


def create_event_by_application_list_url(application_id):
    """
    Creates the URL for the EventByApplicationViewSet list view, replacing
    the application_id parameter with the one provided.

    :param application_id: The id of an application.
    :type application_id: int
    :returns: An URL string for the EventByApplicationViewSet list view.
    :rtype: str
    """
    return reverse('event:events-by-application', kwargs={'application_id': application_id})


def create_application(user, **params):
    """create and return a new application object"""
    # Create a new Deceased instance without parameters
    deceased = Deceased.objects.create(first_name="John", last_name="Doe")
    defaults = {
        'amount': 1000.00,  # Default amount
        'term': 12,  # Default term

        'deceased': deceased,  # Assign the new deceased instance
    }
    defaults.update(params)
    application = Application.objects.create(user=user, **defaults)
    return application


class PublicAPITestCase(APITestCase):
    """
    Test unauthenticated api requests
    """

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email='test@example.com',
            password='testpass123',
        )
        self.client = APIClient()
        self.EVENTS_URL = reverse('event:events-list')
        self.application = create_application(user=self.user)

    def test_login_required_for_getting_all_events(self):
        """Test that the login is required."""
        response = self.client.get(self.EVENTS_URL)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_required_for_getting_filtered_by_application(self):
        """Test that the login is required."""
        url = create_event_by_application_list_url(self.application.pk)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class PrivateAPITestCase(APITestCase):
    """
    Test authenticated API requests
    """

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email='test@example.com',
            password='testpass123',
            is_staff=True,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.EVENTS_URL = reverse('event:events-list')
        self.application = create_application(user=self.user)
        self.other_application = create_application(user=self.user)

    def test_get_all_events(self):
        """Test retrieving all events for the user"""
        event1 = Event.objects.create(
            user=self.user,
            application=self.application,
        )
        event2 = Event.objects.create(
            user=self.user,
            application=self.application,
        )

        response = self.client.get(self.EVENTS_URL)

        # Serialize events manually
        events = Event.objects.all()
        serializer = EventSerializer(events, many=True)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

        # Compare the response data with the manually serialized data
        self.assertEqual(response.data, serializer.data)

        # Compare user and application id in the first and second event
        self.assertEqual(response.data[0]['user'], str(event1.user))
        self.assertEqual(response.data[0]['application'], event1.application.id)
        self.assertEqual(response.data[1]['user'], str(event1.user))
        self.assertEqual(response.data[1]['application'], event2.application.id)

    def test_get_app_specific_events(self):
        """Test retrieving events specific to an application"""

        event1 = Event.objects.create(
            user=self.user,
            application=self.application,
        )
        event2 = Event.objects.create(
            user=self.user,
            application=self.application,
        )

        other_app_event = Event.objects.create(
            user=self.user,
            application=self.other_application,
        )

        url = create_event_by_application_list_url(self.application.pk)
        response = self.client.get(url)

        # Serialize events manually
        events = Event.objects.filter(application=self.application)
        serializer = EventSerializer(events, many=True)

        # Compare the response data with the manually serialized data
        self.assertEqual(response.data, serializer.data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        self.assertNotContains(response, other_app_event)

        # Compare user and application id in the returned events
        self.assertEqual(response.data[0]['user'], str(event1.user))
        self.assertEqual(response.data[0]['application'], event1.application.id)
        self.assertEqual(response.data[1]['user'], str(event2.user))
        self.assertEqual(response.data[1]['application'], event2.application.id)
