"""
Views for the user Api
"""
import logging
import os
from uuid import uuid4

from django.contrib.auth import get_user_model, authenticate
from django.core.exceptions import ObjectDoesNotExist

from django.template.loader import render_to_string
from django.utils.html import strip_tags
from drf_spectacular.utils import extend_schema
from rest_framework import generics, permissions

from rest_framework.exceptions import ValidationError, AuthenticationFailed, PermissionDenied
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from rest_framework import status
from rest_framework.views import APIView

from communications.utils import send_email_f
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

        # Make a mutable copy of request.data
        data = request.data.copy()

        # Add the country to the mutable data
        if country:
            data['country'] = country.upper()

        # Set is_active to False for the activation process
        data['is_active'] = False

        # Generate a unique activation token
        data['activation_token'] = str(uuid4())

        # Serialize the data
        serializer = self.get_serializer(data=data)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            # Optional: Modify error messages if needed
            errors = dict(e.detail)
            for key, value in errors.items():
                if isinstance(value, list):
                    value[:] = [msg.strip().split('.') for msg in value]
            raise ValidationError(errors)

        # Save the user instance
        self.perform_create(serializer)

        # Send activation email after user creation
        user = serializer.instance
        try:
            self.send_activation_email(user, request)
        except Exception as email_error:
            print(f"Failed to send activation email: {email_error}")
            return Response(
                {"error": "User created, but activation email failed to send."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # Return the response
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def send_activation_email(self, user, request):
        """Send an activation email to the user"""
        # Use 'Frontend-Host' header if available, otherwise fallback to 'Host'
        frontend_host = request.headers.get('Frontend-Host', request.headers.get('Host', 'defaultdomain.com'))
        activation_link = f"{frontend_host}/activate/{user.activation_token}"

        # Email details
        subject = f"Activate Your Account - {os.getenv('COMPANY_NAME', 'Default Company Name')}"
        context = {
            "user": user,
            "activation_link": activation_link,
            "company_name": os.getenv('COMPANY_NAME', 'Default Company Name'),
            "support_email": os.getenv('DEFAULT_FROM_EMAIL', 'Default Company Email'),
        }

        # Render HTML email content
        html_message = render_to_string('emails/activation_email.html', context)

        # Send email
        send_email_f(
            sender="noreply@alife.ie",
            recipient=user.email,
            subject=subject,
            message=html_message,
            solicitor_firm=user,
            use_info_email=True
        )


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

    def post(self, request, *args, **kwargs):
        # Get the 'Country' header from the request
        country_header = request.headers.get('Country')

        # Extract email and password from the request data
        email = request.data.get('email')
        password = request.data.get('password')

        # Authenticate the user using email and password
        user = authenticate(request, username=email, password=password)

        if user is None:
            raise AuthenticationFailed("Invalid email or password.")

        # Check if the user's country matches the 'Country' header
        if (not user.is_staff and not user.is_superuser) and user.country != country_header:
            raise PermissionDenied(
                f"Access denied: You are attempting to log in from the {country_header} site, "
                f"but your account is registered for {user.country}. "
                f"Please use the designated website for your registered country.")

        # If validation passes, continue with the default token generation
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data, status=status.HTTP_200_OK)


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


class ActivateUserView(APIView):
    """Endpoint for activating user accounts."""
    authentication_classes = []  # Disable JWT Authentication for this view
    permission_classes = [AllowAny]  # Ensure unauthenticated users can access this

    @extend_schema(
        summary="Activate User Account",
        description="Activate a user account using the activation token.",
        request={"activation_token": str},
        responses={
            200: {"description": "Account activated successfully."},
            400: {"description": "Invalid or missing activation token."},
            404: {"description": "Activation token is invalid or user does not exist."},
        },
        methods=["POST"],  # Specify HTTP method explicitly
    )
    def post(self, request, *args, **kwargs):
        activation_token = request.data.get('activation_token')
        if not activation_token:
            return Response(
                {"detail": "Activation token is required."},
                status=status.HTTP_400_BAD_REQUEST
            )
        print(activation_token)
        try:
            # Find the user with the matching activation token
            user = User.objects.get(activation_token=activation_token)

            if user.is_active:
                return Response(
                    {"detail": "Account is already activated."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            else:
                # Activate the user account
                user.is_active = True
                user.save()

            return Response(
                {"detail": "Account activated successfully."},
                status=status.HTTP_200_OK
            )

        except ObjectDoesNotExist:
            return Response(
                {"detail": "Activation token is invalid or user does not exist."},
                status=status.HTTP_404_NOT_FOUND
            )
