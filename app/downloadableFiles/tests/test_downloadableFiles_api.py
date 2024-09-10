import gc
import os
from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase, APIClient
from django.urls import reverse
import time


class DownloadableFilesAPITest(APITestCase):

    def setUp(self):
        # print(f"\nRunning test: {self._testMethodName}")
        self.staff_user = get_user_model().objects.create_user(
            email='test@example.com',
            password='testpass123',
            is_staff=True,
        )
        self.non_staff_user = get_user_model().objects.create_user(
            email='test1@example.com',
            password='testpass123',
            is_staff=False,
        )
        self.client = APIClient()
        self.list_url = reverse('downloadableFiles:list_files')
        self.add_url = reverse('downloadableFiles:add_file')
        self.delete_url = lambda filename: reverse('downloadableFiles:delete_file', kwargs={'filename': filename})
        self.download_url = lambda filename: reverse('downloadableFiles:download_file', kwargs={'filename': filename})
        self.test_file_name = "test_file.txt"
        self.test_file_path = os.path.join(settings.DOC_DOWNLOAD_DIR, self.test_file_name)

    def tearDown(self):
        # print(f"Finished test: {self._testMethodName}")
        if os.path.exists(self.test_file_path):
            file_removed = False
            max_attempt = 5
            for i in range(max_attempt):
                try:
                    # print(f"Attempting to delete: {self.test_file_path}")
                    os.remove(self.test_file_path)
                    # print("File removed successfully.")
                    file_removed = True
                    break
                except PermissionError as e:
                    # print(f"Deletion failed on attempt {i + 1}. Error: {e}")
                    time.sleep(1)
                    gc.collect()  # Force garbage collection after each attempt
            if not file_removed:
                print(f"Unable to remove file from test {self._testMethodName}, maximum attempts exceeded.")

    def create_test_file(self):
        """Helper function to create a file for testing."""
        with open(self.test_file_path, 'w') as f:
            f.write('Test file content')

    def test_add_file_authorized_staff(self):
        """Test uploading a file with an authorized staff user."""
        self.create_test_file()
        self.client.force_authenticate(user=self.staff_user)
        with open(self.test_file_path, 'rb') as file_data:
            response = self.client.post(self.add_url, {'file': file_data}, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_add_file_authorized_non_staff(self):
        """Test uploading a file with a non-staff user (should fail)."""
        self.create_test_file()
        self.client.force_authenticate(user=self.non_staff_user)
        with open(self.test_file_path, 'rb') as file_data:
            response = self.client.post(self.add_url, {'file': file_data}, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_delete_file_authorized_staff(self):
        """Test deleting a file with an authorized staff user."""
        self.create_test_file()
        self.assertTrue(os.path.exists(self.test_file_path))
        self.client.force_authenticate(user=self.staff_user)
        response = self.client.delete(self.delete_url(self.test_file_name))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(os.path.exists(self.test_file_path))

    def test_delete_file_unauthorized(self):
        """Test deleting a file without authentication (should fail)."""
        self.create_test_file()
        self.assertTrue(os.path.exists(self.test_file_path))
        self.client.force_authenticate(user=None)
        response = self.client.delete(self.delete_url(self.test_file_name))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertTrue(os.path.exists(self.test_file_path))

    def test_download_file_authorized(self):
        """Test downloading a file with an authenticated user."""
        self.create_test_file()
        self.assertTrue(os.path.exists(self.test_file_path))
        self.client.force_authenticate(user=self.staff_user)
        response = self.client.get(self.download_url(self.test_file_name))
        time.sleep(0.5)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_download_file_unauthorized(self):
        """Test downloading a file without authentication (should fail)."""
        self.create_test_file()
        self.client.force_authenticate(user=None)
        response = self.client.get(self.download_url(self.test_file_name))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_files_authorized(self):
        """Test listing files with an authenticated user."""
        self.create_test_file()
        self.client.force_authenticate(user=self.staff_user)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(self.test_file_name, response.json())

    def test_list_files_unauthorized(self):
        """Test listing files without authentication (should fail)."""
        self.create_test_file()
        self.client.force_authenticate(user=None)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
