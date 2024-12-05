"""
Views for the user Api
"""
import logging
import os
from uuid import uuid4

from django.contrib.auth import get_user_model, authenticate

from django.core.exceptions import ObjectDoesNotExist

from django.template.loader import render_to_string
from django.utils.crypto import get_random_string
from django.utils.timezone import now

from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework import generics, permissions

from rest_framework.exceptions import ValidationError, AuthenticationFailed, PermissionDenied, APIException
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from rest_framework import status
from rest_framework.views import APIView

from communications.utils import send_email_f
from core.models import User, OTP
from user.serializers import (UserSerializer,
                              UserListSerializer, UpdatePasswordSerializer, MyTokenObtainPairSerializer,
                              ResetPasswordSerializer, ForgotPasswordSerializer, CheckCredentialsSerializer
                              )
from .permissions import IsStaff

from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.authentication import JWTAuthentication

from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.encoding import force_bytes, force_str
from django.shortcuts import get_object_or_404


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
        # print(f"Country: {country}")

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


logger = logging.getLogger(__name__)


class MyTokenObtainPairView(TokenObtainPairView):
    serializer_class = MyTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        # Get the 'Country' header from the request
        country_header = request.headers.get('Country')

        # Extract email and password from the request data
        email = request.data.get('email')
        password = request.data.get('password')
        otp = request.data.get("otp")

        print(email)

        # Convert OTP list to a string if provided as a list
        if isinstance(otp, list):
            otp = ''.join(otp)  # Convert ['8', '9', '4', '5', '1', '2'] -> '894512'

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

        # Validate the OTP
        if not self.validate_otp(email, otp):
            raise AuthenticationFailed("Invalid verification code.")

        # If validation passes, continue with the default token generation
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data, status=status.HTTP_200_OK)

    def validate_otp(self, email, otp):
        """
        Validate the OTP for the given email.
        Replace this with your actual OTP validation logic (e.g., check against a database or cache).
        """
        # Example logic: Fetch OTP from database or cache and compare
        try:
            otp_record = OTP.objects.get(email=email)
            if otp_record.code == otp:
                # Optional: Check if OTP is still valid
                if not otp_record.is_valid():
                    raise APIException("Verification code has expired.")
                return True
            else:
                return False
        except OTP.DoesNotExist:
            raise APIException("No verification code found for the provided email.")


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
        # print(activation_token)
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


class ForgotPasswordView(APIView):
    """
    Handle sending a password reset email
    """
    authentication_classes = []  # Disable JWT Authentication for this view
    permission_classes = [AllowAny]  # Ensure unauthenticated users can access this

    @extend_schema(
        summary="Request Password Reset",
        description="Send a password reset link to the user's registered email address.",
        request=ForgotPasswordSerializer,
        responses={
            200: {"description": "Password reset link sent to the user's email."},
            400: {"description": "Invalid request or missing email field."},
        },
        methods=["POST"],
    )
    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']

        try:
            user = get_object_or_404(User, email=email)

            # Forbid staff and superuser accounts without making anu users aware that those are valid accounts
            if user.is_staff or user.is_superuser:
                # Return the same generic response as for invalid emails
                return Response(
                    {"detail": "If the account exists, a password reset link has been sent to the email."},
                    status=status.HTTP_200_OK,
                )

            token_generator = PasswordResetTokenGenerator()
            token = token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))

            # Use Frontend-Host header or fallback to a default
            frontend_host = request.headers.get('Frontend-Host', '')
            # print(request.headers)
            reset_link = f"{frontend_host}/reset-password/{uid}/{token}/"

            # Use send_email_f to send the reset email
            context = {
                "reset_link": reset_link,
                "user_name": user.name if user.name else user.email,
                "company_name": os.getenv('COMPANY_NAME', 'Default Company Name'),
                "support_email": os.getenv('DEFAULT_FROM_EMAIL', 'Default Company Email'),
            }

            # Render email content
            message = render_to_string("emails/reset_password_email.html", context)
            send_email_f(
                sender="noreply@alife.ie",
                recipient=email,
                subject="Reset Your Password",
                message=message,
                use_info_email=True,
            )

            return Response({"detail": "Password reset link sent."}, status=status.HTTP_200_OK)

        except User.DoesNotExist:
            # Avoid revealing if the email is invalid to prevent enumeration attacks
            return Response({"detail": "Password reset link sent."}, status=status.HTTP_200_OK)


class CheckCredentialsView(APIView):
    """
    Handle checking user credentials and sending OTP
    """
    authentication_classes = []  # Disable JWT Authentication for this view
    permission_classes = [AllowAny]  # Ensure unauthenticated users can access this

    @extend_schema(
        summary="Check Credentials and Send OTP",
        description=(
                "Validates the user's email and password. If valid, generates a new OTP, "
                "saves it to the database, and sends it to the user's email address."
        ),
        request=CheckCredentialsSerializer,
        responses={
            200: {"description": "OTP sent successfully. The user must verify the OTP."},
            400: {"description": "Invalid credentials provided."},
        },
        methods=["POST"],  # Explicitly specify HTTP method
    )
    def post(self, request):
        serializer = CheckCredentialsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email']
        password = serializer.validated_data['password']

        user = authenticate(email=email, password=password)

        if user:
            # Generate a new OTP
            otp = get_random_string(length=6, allowed_chars='0123456789')

            # Create or update the OTP in the database
            OTP.objects.update_or_create(
                email=email,
                defaults={'code': otp, 'created_at': now()}
            )

            # Render HTML email template
            html_message = render_to_string('emails/otp_email_template.html', {
                'user_name': user.name or email,  # Fallback to email if first_name is not available
                'otp': otp,
                "company_name": os.getenv('COMPANY_NAME', 'Default Company Name'),
                "support_email": os.getenv('DEFAULT_FROM_EMAIL', 'Default Company Email'),
            })

            # Send the OTP via email
            send_email_f(
                sender="noreply@alife.ie",
                recipient=email,
                subject="Your OTP has been sent.",
                message=html_message,
                solicitor_firm=user
            )

            return Response({'otp_required': True}, status=status.HTTP_200_OK)

        return Response({'error': 'Invalid credentials'}, status=status.HTTP_400_BAD_REQUEST)


class ResetPasswordView(APIView):
    """
    Handle password reset using token and uid
    """
    authentication_classes = []  # Disable JWT Authentication for this view
    permission_classes = [AllowAny]  # Ensure unauthenticated users can access this

    @extend_schema(
        summary="Reset Password",
        description="Reset the user's password using the token and uid from the reset link.",
        request=ResetPasswordSerializer,
        responses={
            200: {"description": "Password reset successfully."},
            400: {"description": "Invalid link, token, or missing password field."},
        },
        parameters=[
            OpenApiParameter(
                name="uidb64",
                description="Base64-encoded user ID.",
                required=True,
                type=str,
                location=OpenApiParameter.PATH,
            ),
            OpenApiParameter(
                name="token",
                description="Password reset token.",
                required=True,
                type=str,
                location=OpenApiParameter.PATH,
            ),
        ],
        methods=["POST"],
    )
    def post(self, request, uidb64: str, token: str):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_password = serializer.validated_data['password']

        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            return Response({"detail": "Invalid link."}, status=status.HTTP_400_BAD_REQUEST)

        token_generator = PasswordResetTokenGenerator()
        if not token_generator.check_token(user, token):
            return Response({"detail": "Invalid or expired token."}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_password)
        user.save()

        # Optional: Send a confirmation email
        message = render_to_string("emails/reset_password_confirmation.html",
                                   {"user_name": user.name or user.email,
                                    "company_name": os.getenv('COMPANY_NAME', 'Default Company Name'),
                                    "support_email": os.getenv('DEFAULT_FROM_EMAIL', 'Default Company Email'), })
        send_email_f(
            sender="noreply@alife.ie",
            recipient=user.email,
            subject="Password Reset Successful",
            message=message,
            use_info_email=True,
        )

        return Response({"detail": "Password reset successfully."}, status=status.HTTP_200_OK)
