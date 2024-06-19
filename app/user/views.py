"""
Views for the user Api
"""

from rest_framework import generics, authentication, permissions
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.settings import api_settings

from core.models import User
from user.serializers import (UserSerializer,
                              AuthTokenSerializer, UserListSerializer
                              )


class UserList(generics.ListAPIView):
    """View for listing all users in the system"""
    queryset = User.objects.all()
    serializer_class = UserListSerializer
    authentication_classes = (authentication.TokenAuthentication,)
    permission_classes = (permissions.IsAuthenticated,)


class CreateUserView(generics.CreateAPIView):
    """Create a new user in the system"""
    serializer_class = UserSerializer


class CreateTokenView(ObtainAuthToken):
    """Create a new auth token"""
    serializer_class = AuthTokenSerializer
    renderer_classes = api_settings.DEFAULT_RENDERER_CLASSES


class ManageUserView(generics.RetrieveUpdateAPIView):
    """Manage the authenticated user"""
    serializer_class = UserSerializer
    authentication_classes = (authentication.TokenAuthentication,)
    permission_classes = (permissions.IsAuthenticated,)

    def get_object(self):
        """Retrieve the authenticated user"""
        return self.request.user


# list only solicitors
class UserListNonStaff(generics.ListAPIView):
    """View for listing all non-staff users in the system"""
    serializer_class = UserListSerializer
    authentication_classes = (authentication.TokenAuthentication,)
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        """Return only non-staff users"""
        return User.objects.filter(is_staff=False)
