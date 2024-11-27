"""
Views for the user Api
"""
import logging

from django.contrib.auth import get_user_model
from rest_framework import generics, permissions
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.settings import api_settings
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from rest_framework import status

from core.models import User
from user.serializers import (UserSerializer,
                              UserListSerializer, UpdatePasswordSerializer, MyTokenObtainPairSerializer
                              )
from .permissions import IsStaff

from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.authentication import JWTAuthentication


class UserList(generics.ListAPIView):
    """View for listing all users in the system.
        Access To this api is only for is_staff users
    """
    queryset = User.objects.all()
    serializer_class = UserListSerializer
    authentication_classes = (JWTAuthentication,)
    permission_classes = (permissions.IsAuthenticated, IsStaff,)


class CreateUserView(generics.CreateAPIView):
    """Create a new user in the system"""
    serializer_class = UserSerializer

    def create(self, request, *args, **kwargs):
        # Extract the Country header
        country = request.headers.get('Country')
        print(f"Country: {country}")

        # Add the country to the request data if it exists
        if country:
            request.data['country'] = country.upper()
        print(f"Request data: {request.data}")
        serializer = self.get_serializer(data=request.data)

        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            errors = dict(e.detail)  # Replace 'e' with 'e.detail'
            for key, value in errors.items():
                if isinstance(value, list):
                    for i, message in enumerate(value):
                        sentences = [sent.strip() for sent in message.split('.')]
                        value[i] = sentences
            raise ValidationError(errors)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


class UpdatePasswordView(generics.UpdateAPIView):
    serializer_class = UpdatePasswordSerializer
    model = get_user_model()
    authentication_classes = (JWTAuthentication,)
    permission_classes = (permissions.IsAuthenticated,)

    def get_object(self):
        """
        This method returns the logged in user
        """
        return self.request.user

    def update(self, request, *args, **kwargs):
        self.object = self.get_object()
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            # Check old password
            old_password = serializer.data.get("old_password")
            if not self.object.check_password(old_password):
                return Response({"old_password": ["Wrong password."]}, status=status.HTTP_400_BAD_REQUEST)
            # Set new password
            self.object.set_password(serializer.data.get("new_password"))
            self.object.save()

            return Response("Password updated successfully", status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# class CreateTokenView(ObtainAuthToken):
#     """Create a new auth token"""
#     serializer_class = AuthTokenSerializer
#     renderer_classes = api_settings.DEFAULT_RENDERER_CLASSES

logger = logging.getLogger(__name__)


class MyTokenObtainPairView(TokenObtainPairView):
    serializer_class = MyTokenObtainPairSerializer


class ManageUserView(generics.RetrieveUpdateAPIView):
    """Manage the authenticated user"""
    serializer_class = UserSerializer
    authentication_classes = (JWTAuthentication,)
    permission_classes = (permissions.IsAuthenticated,)

    def get_object(self):
        """Retrieve the authenticated user"""
        return self.request.user

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            errors = dict(e.detail)  # Replace 'e' with 'e.detail'
            for key, value in errors.items():
                if isinstance(value, list):
                    for i, message in enumerate(value):
                        sentences = [sent.strip() for sent in message.split('.')]
                        value[i] = sentences
            raise ValidationError(errors)
        self.perform_update(serializer)
        return Response(serializer.data)


# list only solicitors
class UserListNonStaff(generics.ListAPIView):
    """View for listing all non-staff users in the system.
        Access To this api is only for is_staff users
    """
    serializer_class = UserListSerializer
    authentication_classes = (JWTAuthentication,)
    permission_classes = (permissions.IsAuthenticated, IsStaff,)

    def get_queryset(self):
        """Return only non-staff users"""
        return User.objects.filter(is_staff=False)


# get user by id for all the users but api access restricted to stall
class RetrieveUserView(generics.RetrieveAPIView):
    """View for retrieving a user by ID.
        Access To this api is only for is_staff users
    """
    serializer_class = UserSerializer
    authentication_classes = (JWTAuthentication,)
    permission_classes = (permissions.IsAuthenticated, IsStaff,)
    queryset = get_user_model().objects.all()
