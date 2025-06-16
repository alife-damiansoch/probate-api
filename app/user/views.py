"""
Views for the user Api
"""
import logging
import os
import io
from datetime import timedelta

import pyotp
from drf_spectacular.types import OpenApiTypes
from qrcode.main import QRCode
from uuid import uuid4
from rest_framework import status
import secrets
from django.core.cache import cache

from django.contrib.auth import get_user_model

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
from core.Validators.phone_numbers_validators import PhoneNumberValidator
from core.Validators.postcode_validators import PostcodeValidator
from core.models import User, OTP, AuthenticatorSecret, FrontendAPIKey
from user.serializers import (UserSerializer,
                              UserListSerializer, UpdatePasswordSerializer, MyTokenObtainPairSerializer,
                              ResetPasswordSerializer, ForgotPasswordSerializer, CheckCredentialsSerializer,
                              UpdateAuthMethodSerializer
                              )
from .permissions import IsStaff

from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.tokens import RefreshToken
from core.throttling import CombinedThrottle

from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.encoding import force_bytes, force_str
from django.shortcuts import get_object_or_404

from .utils import validate_otp, validate_authenticator_code, custom_authenticate

from rest_framework.exceptions import ValidationError as DRFValidationError


class UserList(generics.ListAPIView):
    """View for listing all users in the system.
        Access To this api is only for is_staff users
    """
    queryset = User.objects.all()
    serializer_class = UserListSerializer
    authentication_classes = (JWTAuthentication,)
    permission_classes = (permissions.IsAuthenticated, IsStaff,)


class CreateUserView(generics.CreateAPIView):
    """
    Create a new user in the system with throttling.
    """
    throttle_classes = [CombinedThrottle]
    throttle_scope = "registration"

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

        # Validate eircode
        # Check if address is provided
        address = data.get('address')
        if not address:
            raise ValidationError({"address": "Address is required."})

        # Check if eircode is provided in the address
        eircode = address.get('eircode')
        if not eircode:
            raise ValidationError({"eircode": "Eircode is required in the address."})

        try:
            PostcodeValidator.validate(eircode.strip(), country.upper())
        except ValidationError as e:
            raise e

        # validate phone number
        phone_number = data['phone_number']
        try:
            # Validate phone number
            PhoneNumberValidator.validate(phone_number, country)
        except ValidationError as e:
            # DRF automatically formats this error as a plain string or JSON response
            raise e

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
            use_info_email=True,
            save_in_email_log=False
        )


class UpdatePasswordView(generics.UpdateAPIView):
    """
        Allows users to update their password with throttling.
    """
    throttle_classes = [CombinedThrottle]
    throttle_scope = "password_change"

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
    """
      Handles user login with throttling to prevent brute force attacks.
      """
    throttle_classes = [CombinedThrottle]
    throttle_scope = "login"
    serializer_class = MyTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        # Get the 'Country' header from the request
        country_header = request.headers.get('Country')

        # Extract email, password, and code (OTP or Authenticator)
        email = request.data.get('email')
        password = request.data.get('password')

        code = request.data.get("otp")  # 'otp' field is used for both OTP and Authenticator code

        # Convert OTP list to a string if provided as a list
        if isinstance(code, list):
            code = ''.join(code)  # Convert ['8', '9', '4', '5', '1', '2'] -> '894512'

        # Authenticate the user using email and password
        user = custom_authenticate(request, email=email, password=password)

        if user is None:
            raise AuthenticationFailed("Invalid email or password.")

        if not user.is_staff and not user.is_superuser and not code:
            raise AuthenticationFailed("Request blocked")

        if not user.is_staff and not user.is_superuser:

            # Validate the code based on the user's preferred authentication method
            if user.preferred_auth_method == 'otp':
                if not validate_otp(email, code):
                    raise AuthenticationFailed("Invalid verification code.")
            elif user.preferred_auth_method == 'authenticator':
                if not validate_authenticator_code(user, code):
                    raise AuthenticationFailed("Invalid authenticator code.")
            else:
                raise AuthenticationFailed("Unsupported authentication method.")

        # Check if the user's country matches the 'Country' header
        if (not user.is_staff and not user.is_superuser) and user.country != country_header:
            raise PermissionDenied(
                f"Access denied: You are attempting to log in from the {country_header} site, "
                f"but your account is registered for {user.country}. "
                f"Please use the designated website for your registered country."
            )

        # Generate access & refresh tokens
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)
        refresh_token = str(refresh)

        # ✅ Delete any existing API key for the user
        FrontendAPIKey.objects.filter(user=user).delete()

        # ✅ Generate a new API key
        api_key, created = FrontendAPIKey.objects.update_or_create(
            user=user,
            defaults={"key": secrets.token_urlsafe(32), "expires_at": now() + timedelta(minutes=15)}
        )

        # Prepare response data
        response_data = {
            "access": access_token,
            "refresh": refresh_token,
            "api_key": api_key.key,  # Include API key in response
            "user_type": "staff" if user.is_staff else "regular"  # Help frontend know which type
        }

        response = Response(response_data, status=status.HTTP_200_OK)

        # Set HttpOnly API key cookie (still set for browsers that support it)
        cookie_name = "X-Frontend-API-Key" if not user.is_staff else "X-Frontend-API-Key-Agents"
        response.set_cookie(
            key=cookie_name,
            value=api_key.key,
            httponly=True,
            secure=True,  # Set to True in production (requires HTTPS)
            samesite="Strict",  # Changed from "None" to "Strict"
            path="/",
        )

        return response


class MobileTokenObtainPairViewForSolicitors(TokenObtainPairView):
    """
      Handles user login with throttling to prevent brute force attacks.
      """
    throttle_classes = [CombinedThrottle]
    throttle_scope = "login"
    serializer_class = MyTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        # Get the 'Country' header from the request
        country_header = request.headers.get('Country')

        # Extract email and password
        email = request.data.get('email')
        password = request.data.get('password')

        # Authenticate the user using email and password
        user = custom_authenticate(request, email=email, password=password)

        if user is None:
            raise AuthenticationFailed("Invalid email or password.")

        if user.is_staff or user.is_superuser:
            raise AuthenticationFailed("Request blocked")

        # Check if the user's country matches the 'Country' header
        if (not user.is_staff and not user.is_superuser) and user.country != country_header:
            raise PermissionDenied(
                f"Access denied: You are attempting to log in from the {country_header} site, "
                f"but your account is registered for {user.country}. "
                f"Please use the designated website for your registered country."
            )

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

        # Print all cookies from the request
        # print("Cookies received:", self.request.COOKIES)
        return self.request.user

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        try:

            serializer.is_valid(raise_exception=True)
            # validate phone number
            phone_number = request.data['phone_number']
            # print(instance)
            country = instance.country

            # Validate eircode
            # Check if address is provided
            address = request.data['address']
            print(address, country)
            if not address:
                raise ValidationError({"address": "Address is required."})

            # Check if eircode is provided in the address
            eircode = address.get('eircode')
            if not eircode:
                raise ValidationError({"eircode": "Eircode is required in the address."})

            try:
                PostcodeValidator.validate(eircode.strip(), country.upper())
            except DRFValidationError as e:
                # Handle DRFValidationError properly
                if isinstance(e.detail, list):  # Check if the detail is a list
                    raise DRFValidationError({"eircode": e.detail[0]})
                raise e

            try:
                # Validate phone number
                PhoneNumberValidator.validate(phone_number, country)
            except ValidationError as e:
                # DRF automatically formats this error as a plain string or JSON response
                raise e
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
    """
    Endpoint for activating user accounts.
    """
    throttle_classes = [CombinedThrottle]
    throttle_scope = "activation"

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
                # Clear the activation token
                user.activation_token = None
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
                save_in_email_log=False
            )

            return Response({"detail": "Password reset link sent."}, status=status.HTTP_200_OK)

        except User.DoesNotExist:
            # Avoid revealing if the email is invalid to prevent enumeration attacks
            return Response({"detail": "Password reset link sent."}, status=status.HTTP_200_OK)


def generate_authenticator_secret(user, secret):
    """
    Generates or updates an authenticator secret for a user and returns the QR code binary data.
    """
    authenticator, created = AuthenticatorSecret.objects.update_or_create(
        user=user,
        defaults={'secret': secret, 'is_active': False}
    )

    totp = pyotp.TOTP(secret)
    provisioning_url = totp.provisioning_uri(
        name=user.email,
        issuer_name=os.getenv('COMPANY_NAME', 'Default Company Name')
    )
    qr = QRCode(box_size=10, border=5)
    qr.add_data(provisioning_url)
    qr.make(fit=True)

    # Convert QR code to an image
    qr_image = io.BytesIO()
    qr_code_image = qr.make_image(fill_color="black", back_color="white", kind="PNG")  # Use the `kind` property
    qr_code_image.save(qr_image)
    qr_image.seek(0)
    qr_code_binary = qr_image.read()
    return qr_code_binary


def generate_otp_and_send_email(email, user):
    otp = get_random_string(length=6, allowed_chars='0123456789')
    OTP.objects.update_or_create(
        email=email,
        defaults={'code': otp, 'created_at': now()}
    )

    html_message = render_to_string('emails/otp_email_template.html', {
        'user_name': user.name or email,
        'otp': otp,
        "company_name": os.getenv('COMPANY_NAME', 'Default Company Name'),
        "support_email": os.getenv('DEFAULT_FROM_EMAIL', 'Default Company Email'),
    })

    send_email_f(
        sender="noreply@alife.ie",
        recipient=email,
        subject="Your OTP has been sent.",
        message=html_message,
        solicitor_firm=user,
        save_in_email_log=False
    )


class CheckCredentialsView(APIView):
    """
    Handle checking user credentials and sending OTP or setting up Authenticator App

      Handles user login with throttling to prevent brute force attacks.
      """
    throttle_classes = [CombinedThrottle]  # Enable throttling
    throttle_scope = "login"  # Apply "login" throttle settings from settings.py

    authentication_classes = []  # Disable JWT Authentication for this view
    permission_classes = [AllowAny]  # Ensure unauthenticated users can access this

    @extend_schema(
        summary="Check Credentials and Handle OTP or Authenticator Setup",
        description=(
                "Validates the user's email and password. Handles OTP generation and "
                "sending or provides Authenticator App setup/validation."
        ),
        request=CheckCredentialsSerializer,
        responses={
            200: {"description": "OTP sent successfully or Authenticator setup returned."},
            400: {"description": "Invalid credentials provided."},
        },
        methods=["POST"],
    )
    def post(self, request):
        serializer = CheckCredentialsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email']
        password = serializer.validated_data['password']

        # Check if the user exists
        try:
            user = User.objects.get(email=email)
            if not user.is_active:
                return Response(
                    {"detail": "Your account is inactive.",
                     "detail2": " Please activate your account before logging in."},
                    status=status.HTTP_403_FORBIDDEN
                )
        except ObjectDoesNotExist:
            # Optional: Provide a message if the email is not registered
            print(f"User with email {email} does not exist.")

        # Authenticate the user
        user = custom_authenticate(request, email=email, password=password)

        if not user:
            raise AuthenticationFailed("Invalid email or password.")

        if user.is_staff:
            raise AuthenticationFailed("Not permitted")

        # Handle OTP
        if user.preferred_auth_method == 'otp':
            generate_otp_and_send_email(email, user)
            return Response({'auth_method': 'otp', 'otp_required': True}, status=status.HTTP_200_OK)

        # Handle Authenticator App
        elif user.preferred_auth_method == 'authenticator':
            # Check if the authenticator secret already exists
            authenticator = AuthenticatorSecret.objects.filter(user=user).first()
            if not authenticator or authenticator.is_active is False:
                # Generate a new secret for the user
                secret = pyotp.random_base32()
                qr_code_binary = generate_authenticator_secret(user, secret)

                return Response({
                    'auth_method': 'authenticator',
                    'manual_key': secret,
                    'qr_code': qr_code_binary.decode('latin1', ),  # Return QR code as a binary string
                    'authenticator_required': True
                }, status=status.HTTP_200_OK)
            else:
                # If the authenticator is already set up, prompt for a 6-digit code
                return Response({'auth_method': 'authenticator', 'authenticator_required': True},
                                status=status.HTTP_200_OK)

        return Response({'error': 'Unsupported authentication method.'}, status=status.HTTP_400_BAD_REQUEST)


class UpdateAuthMethodView(APIView):
    """
    Allows updating the preferred authentication method (OTP or Authenticator).
    """
    authentication_classes = []  # Disable JWT Authentication for this view
    permission_classes = [AllowAny]  # Ensure unauthenticated users can access this

    @extend_schema(
        summary="Update Preferred Authentication Method",
        description=(
                "Allows a user to update their preferred authentication method to either OTP or Authenticator App. "
                "Checks for existing OTPs or Authenticator setup and sets up as required."
        ),
        request=UpdateAuthMethodSerializer,
        responses={
            200: {"description": "Preferred authentication method updated successfully."},
            400: {"description": "Invalid email or unsupported authentication method."},
        },
        methods=["POST"],
    )
    def post(self, request):

        serializer = UpdateAuthMethodSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email']
        preferred_auth_method = serializer.validated_data['preferred_auth_method']

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(
                {"error": "User with this email does not exist."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if preferred_auth_method == 'otp':
            # Handle OTP switching
            try:
                otp_record = OTP.objects.get(email=email)
                if not otp_record.is_valid():
                    # Generate a new OTP and send it
                    generate_otp_and_send_email(email, user)
            except OTP.DoesNotExist:
                # If no OTP exists, create and send it
                otp = get_random_string(length=6, allowed_chars='0123456789')
                OTP.objects.create(email=email, code=otp, created_at=now())

                html_message = render_to_string('emails/otp_email_template.html', {
                    'user_name': user.name or email,
                    'otp': otp,
                    "company_name": os.getenv('COMPANY_NAME', 'Default Company Name'),
                    "support_email": os.getenv('DEFAULT_FROM_EMAIL', 'Default Company Email'),
                })

                send_email_f(
                    sender="noreply@alife.ie",
                    recipient=email,
                    subject="Your OTP has been sent.",
                    message=html_message,
                    solicitor_firm=user,
                    save_in_email_log=False
                )
            user.preferred_auth_method = 'otp'
            user.save()
            return Response(
                {"auth_method": "otp", "message": "OTP method selected and email sent if necessary."},
                status=status.HTTP_200_OK,
            )

        elif preferred_auth_method == 'authenticator':
            # Handle Authenticator switching
            authenticator = AuthenticatorSecret.objects.filter(user=user).first()
            if not authenticator or not authenticator.is_active:
                # generate and email OTP for user verification
                otp_record = OTP.objects.get(email=email)

                generate_otp_and_send_email(email, user)
                # Generate a new secret
                secret = pyotp.random_base32()
                qr_code_binary = generate_authenticator_secret(user, secret)

                user.preferred_auth_method = 'authenticator'
                user.save()

                return Response({
                    "auth_method": "authenticator",
                    "manual_key": secret,
                    "qr_code": qr_code_binary.decode('latin1'),
                    "message": "Authenticator setup created successfully.",
                }, status=status.HTTP_200_OK)

            # Authenticator already set up
            user.preferred_auth_method = 'authenticator'
            user.save()
            return Response(
                {"auth_method": "authenticator", "message": "Authenticator method selected."},
                status=status.HTTP_200_OK,
            )

        return Response(
            {"error": "Unsupported authentication method."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    @extend_schema(
        summary="Check Current Authentication Status",
        description=(
                "Checks the current status of the user's preferred authentication method. "
                "Returns whether the authenticator is active, along with QR code and manual key if applicable."
        ),
        parameters=[
            OpenApiParameter(
                name="email",
                description="User's email address.",
                required=True,
                type=str,
                location=OpenApiParameter.QUERY,
            )
        ],
        responses={
            200: {
                "description": "Current authentication status retrieved successfully.",
                "content": {
                    "application/json": {
                        "example": {
                            "auth_method": "authenticator",
                            "is_active": False,
                            "manual_key": "ABCDEF123456",
                            "qr_code": "base64encodedimage",
                            "message": "Authenticator setup needs activation.",
                        }
                    }
                },
            },
            400: {"description": "Missing or invalid email parameter."},
            404: {"description": "User not found."},
        },
        methods=["GET"],
    )
    def get(self, request):
        email = request.query_params.get("email")
        if not email:
            return Response({"error": "Email parameter is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email=email)
            if user.preferred_auth_method == "authenticator":
                authenticator = AuthenticatorSecret.objects.filter(user=user).first()
                if authenticator and not authenticator.is_active:
                    totp = pyotp.TOTP(authenticator.secret)
                    qr_code_binary = generate_authenticator_secret(user, authenticator.secret)
                    return Response({
                        "auth_method": "authenticator",
                        "is_active": False,
                        "manual_key": authenticator.secret,
                        "qr_code": qr_code_binary.decode('latin1'),
                        "message": "Authenticator setup needs activation.",
                    }, status=status.HTTP_200_OK)

                return Response({
                    "auth_method": "authenticator",
                    "is_active": True,
                    "message": "Authenticator is active.",
                }, status=status.HTTP_200_OK)

            return Response({
                "auth_method": user.preferred_auth_method,
                "is_active": True,
                "message": f"{user.preferred_auth_method.capitalize()} method is active.",
            }, status=status.HTTP_200_OK)

        except User.DoesNotExist:
            return Response({"error": "User not found."}, status=status.HTTP_404_NOT_FOUND)


class ResetPasswordView(APIView):
    """
    Handle password reset using token and uid with  throttling
    """
    throttle_classes = [CombinedThrottle]
    throttle_scope = "password_reset"

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
            save_in_email_log=False
        )

        return Response({"detail": "Password reset successfully."}, status=status.HTTP_200_OK)


class VerifyAuthenticatorCodeView(APIView):
    """
    Verify the code from the authenticator app and activate the secret.
    """
    throttle_classes = [CombinedThrottle]
    throttle_scope = "authenticator_verification"

    authentication_classes = []  # Disable JWT Authentication for this view
    permission_classes = [AllowAny]  # Ensure unauthenticated users can access this

    @extend_schema(
        summary="Verify Authenticator Code",
        description=(
                "Validates the 6-digit code entered by the user from their authenticator app. "
                "If the code is correct, the authenticator secret is activated and set as the preferred method."
        ),
        request={
            "type": "object",
            "properties": {
                "email": {"type": "string", "format": "email", "description": "User's email address."},
                "code": {"type": "string", "maxLength": 6, "description": "6-digit code from the authenticator app."},
            },
            "required": ["email", "code"],
        },
        responses={
            200: {"description": "Authenticator app successfully activated."},
            400: {"description": "Invalid verification code."},
            404: {"description": "User not found or no inactive authenticator secret found."},
        },
        methods=["POST"],  # Explicitly specify HTTP method
    )
    def post(self, request):
        email = request.data.get('email')
        code = request.data.get('code')

        # Convert OTP list to a string if provided as a list
        if isinstance(code, list):
            code = ''.join(code)  # Convert ['8', '9', '4', '5', '1', '2'] -> '894512'

        try:
            user = User.objects.get(email=email)
            authenticator = AuthenticatorSecret.objects.get(user=user, is_active=False)  # Only check inactive secrets
            totp = pyotp.TOTP(authenticator.secret)

            if totp.verify(code):
                authenticator.is_active = True  # Mark as active
                authenticator.save()
                user.preferred_auth_method = 'authenticator'  # Set as preferred method
                user.save()
                return Response({"message": "Authenticator app successfully activated."}, status=status.HTTP_200_OK)
            else:
                return Response({"error": "Invalid verification code."}, status=status.HTTP_400_BAD_REQUEST)

        except User.DoesNotExist:
            return Response({"error": "User not found."}, status=status.HTTP_404_NOT_FOUND)
        except AuthenticatorSecret.DoesNotExist:
            return Response({"error": "No inactive authenticator secret found."}, status=status.HTTP_404_NOT_FOUND)


class ValidateOtpView(APIView):
    """
    API endpoint to validate an OTP for a given email.
    """
    throttle_classes = [CombinedThrottle]
    throttle_scope = "otp_verification"

    authentication_classes = []  # Disable authentication for this endpoint
    permission_classes = []  # Allow unauthenticated users

    @extend_schema(
        summary="Validate OTP",
        description="Validates a one-time password (OTP) for a given email address.",
        request={
            "type": "object",
            "properties": {
                "email": {"type": "string", "format": "email", "description": "User's email address."},
                "otp": {"type": "string", "description": "One-time password to validate."},
            },
            "required": ["email", "otp"],
        },
        responses={
            200: {"description": "OTP is valid."},
            400: {"description": "Invalid OTP or expired."},
        },
    )
    def post(self, request):
        email = request.data.get('email')
        otp = request.data.get('otp')
        # Convert OTP list to a string if provided as a list
        if isinstance(otp, list):
            otp = ''.join(otp)  # Convert ['8', '9', '4', '5', '1', '2'] -> '894512'

        if not email or not otp:
            return Response({"error": "Email and OTP are required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            if validate_otp(email, otp):
                return Response({"message": "OTP is valid."}, status=status.HTTP_200_OK)
            else:
                return Response({"error": "Invalid OTP."}, status=status.HTTP_400_BAD_REQUEST)
        except APIException as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class LogoutView(APIView):
    """Logout view that deletes the API key and clears cookies."""
    authentication_classes = (JWTAuthentication,)
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request):
        # ✅ Delete the API key
        if request.user.is_authenticated:
            FrontendAPIKey.objects.filter(user=request.user).delete()

        response = Response({"message": "Logged out"}, status=200)

        # ✅ Remove API key cookie (Ensure it's properly deleted for cross-site requests)
        response.delete_cookie("X-Frontend-API-Key", samesite="None")

        return response


class RefreshAPIKeyView(APIView):
    """Refresh API key expiration time by 15 minutes."""
    authentication_classes = (JWTAuthentication,)
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request):
        user = request.user

        try:
            # ✅ Extend API key expiration time by 15 minutes
            key_obj = FrontendAPIKey.objects.get(user=user)
            key_obj.expires_at = now() + timedelta(minutes=15)
            key_obj.save(update_fields=["expires_at"])

            return Response(
                {"message": "API key extended", "expires_at": key_obj.expires_at.isoformat()},
                status=200
            )
        except FrontendAPIKey.DoesNotExist:
            return Response({"error": "API key not found"}, status=404)
