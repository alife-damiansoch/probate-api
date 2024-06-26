"""
Test comment api
"""
import json

from django.contrib.auth import get_user_model

from django.urls import reverse

from rest_framework import status
from rest_framework.test import APIClient, APITestCase

import user
from core.models import (Event, Application, Deceased, Comment, )
from comment.serializers import CommentSerializer


def create_comment(user, application, **params):
    """create and return comment object"""
    defaults = {
        "text": "Default comment",

    }
    defaults.update(params)
    comment = Comment.objects.create(application=application, created_by=user, **defaults)
    return comment


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


def get_comment_detail_url(comment_id):
    return reverse('comment:comment-detail', kwargs={'pk': comment_id})


class PublicCommentAPITestCase(APITestCase):
    """
    Test unauthenticated comment api requests
    """

    def setUp(self):
        self.client = APIClient()
        self.COMMENT_LIST_URL = reverse('comment:comment-list')

    def test_login_required(self):
        """Test that login is required for comments"""

        response = self.client.get(self.COMMENT_LIST_URL)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_isStaff_true_is_required(self):
        """Test that only staff users are allowed"""
        user = get_user_model().objects.create_user(
            email='test@example.com',
            password='testpass',
            is_staff=False
        )

        self.client.force_authenticate(user=user)

        response = self.client.get(self.COMMENT_LIST_URL)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class PrivateCommentAPITestCase(APITestCase):
    """Test authenticated comment api requests"""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email='test@example.com',
            password='testpass',
            is_staff=True
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.application = create_application(user=self.user)
        self.COMMENT_LIST_URL = reverse('comment:comment-list')

    def test_retrieve_comments_list(self):
        comment1 = create_comment(user=self.user, application=self.application)
        comment2 = create_comment(user=self.user, application=self.application)

        response = self.client.get(self.COMMENT_LIST_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        comments = Comment.objects.all().order_by("-id")
        serializer = CommentSerializer(comments, many=True)
        self.assertEqual(response.data, serializer.data)

        # Convert to set for efficient item presence check
        response_data_items_set = {frozenset(item.items()) for item in response.data}

        # Check if comment1 and comment2 are in the response
        self.assertIn(frozenset(CommentSerializer(comment1).data.items()), response_data_items_set)
        self.assertIn(frozenset(CommentSerializer(comment2).data.items()), response_data_items_set)

    def test_create_comment_successful(self):
        """Test creating a new comment"""
        url = self.COMMENT_LIST_URL
        payload = {'application': self.application.id, 'text': 'Test comment'}

        res = self.client.post(url, payload)

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        comments = Comment.objects.all().order_by("-id")

        self.assertEqual(len(comments), 1)
        comment = comments[0]
        serializer = CommentSerializer(comment)
        self.assertEqual(serializer.data, res.data)
        self.assertEqual(comment.text, 'Test comment')
        self.assertEqual(comment.created_by, self.user)
        self.assertEqual(comment.application_id, self.application.id)
        self.assertEqual(comment.updated_by, None)

    def test_update_comment_successful(self):
        """Test updating an existing comment"""

        # Create Application and Comment
        application = create_application(user=self.user)
        comment = create_comment(user=self.user, application=application)

        # Generate URL
        url = get_comment_detail_url(comment.id)
        payload = {'text': 'Updated comment'}

        # Send PATCH request
        res = self.client.patch(url, payload, format='json')

        # Assertions
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        comment.refresh_from_db()
        self.assertEqual(comment.text, 'Updated comment')
        self.assertEqual(comment.updated_by, self.user)

    def test_delete_comment_successful(self):
        """Test deleting an existing comment"""
        app = create_application(user=self.user)
        comment = create_comment(user=self.user, application=app)

        url = get_comment_detail_url(comment_id=comment.id)

        res = self.client.delete(url)

        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        comments = Comment.objects.all()
        self.assertEqual(len(comments), 0)

    def test_filter_by_application(self):
        """Test filtering comments by the application"""
        application1 = create_application(self.user)
        application2 = create_application(self.user)
        comment1_for_application1 = create_comment(user=self.user, application=application1)
        comment2_for_application1 = create_comment(user=self.user, application=application1)
        comment1_for_application2 = create_comment(user=self.user, application=application2)
        comment2_for_application2 = create_comment(user=self.user, application=application2)

        url = f'{self.COMMENT_LIST_URL}?application={application1.id}'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Serialize the expected comments
        serializer1 = CommentSerializer(comment1_for_application1)
        serializer2 = CommentSerializer(comment2_for_application1)

        # Check if the response data contains the expected comments
        self.assertIn(serializer1.data, response.data)
        self.assertIn(serializer2.data, response.data)

        # Check that the response data does not contain comments from other applications
        serializer3 = CommentSerializer(comment1_for_application2)
        serializer4 = CommentSerializer(comment2_for_application2)
        self.assertNotIn(serializer3.data, response.data)
        self.assertNotIn(serializer4.data, response.data)
