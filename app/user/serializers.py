"""Serializers for the User Api view"""

from rest_framework import serializers
from django.contrib.auth import (get_user_model, authenticate, )
from django.utils.translation import gettext as _
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from core.models import Team, Address, User, Application, Loan, AssociatedEmail

import re

from django.core.exceptions import ValidationError

from user.utils import validate_user_password


# this serializer is only created to return extra info in the list user
class LoanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Loan
        fields = '__all__'  # Adjust the fields as per your requirement


# this serializer is only created to return extra info in the list user
class ApplicationSerializer(serializers.ModelSerializer):
    loan = LoanSerializer(read_only=True)
    country = serializers.SerializerMethodField()  # Add the custom field

    class Meta:
        model = Application
        fields = '__all__'

    def get_country(self, obj):
        # Access the related user's country
        return obj.user.country if obj.user else None


class TeamSerializer(serializers.ModelSerializer):
    class Meta:
        model = Team
        fields = "__all__"


class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = "__all__"


class UserListSerializer(serializers.ModelSerializer):
    teams = serializers.SerializerMethodField()  # Use SerializerMethodField for custom behavior
    applications = serializers.SerializerMethodField()

    class Meta:
        model = get_user_model()
        fields = ['id', 'email', 'name', 'teams', 'is_active', 'is_staff', 'is_superuser', 'applications', "country"]
        read_only_fields = fields

    def get_teams(self, user):
        """Serialize teams with the full TeamSerializer."""
        return TeamSerializer(user.teams.all(), many=True).data

    def get_applications(self, user):
        applications = Application.objects.filter(assigned_to=user)
        return ApplicationSerializer(applications, many=True).data


class UserSerializer(serializers.ModelSerializer):
    """Serializer for the User model"""
    address = AddressSerializer(required=False, default=None)
    teams = TeamSerializer(many=True, required=False, default=None)

    class Meta:
        model = get_user_model()
        fields = ['id', 'email', 'password', 'name', 'phone_number', 'address', 'teams', 'is_active', 'is_staff',
                  'is_superuser', 'country', 'activation_token']
        extra_kwargs = {'password': {'write_only': True}}
        read_only_fields = ('id', 'is_active', 'is_staff', 'is_superuser', 'teams',)

    def validate_password(self, value):
        """
        Validate password using the utility function.
        """
        try:
            validate_user_password(value, user=self.instance)  # Pass the user instance for similarity checks
        except DjangoValidationError as e:
            raise serializers.ValidationError(e.messages)  # Convert to DRF's ValidationError
        return value

    def create(self, validated_data):
        password = validated_data.pop('password', None)
        if 'address' in validated_data:  # check if address is in validated_data
            address_data = validated_data.pop('address')
            if address_data is not None:  # if address_data is not None, then create Address instance
                address = Address.objects.create(**address_data)
            else:
                address = None  # assigning None to address if address_data is None
        else:
            address = None  # if no address is provided in validated_data, assign None to address

        validated_data.pop('teams')

        phone_number = validated_data.pop('phone_number', None)
        if phone_number and not phone_number.startswith('+'):
            phone_number = '+353' + phone_number.lstrip('0')
        validated_data['phone_number'] = phone_number

        # Validate the password before creating the user
        if password:
            try:
                validate_user_password(password)  # Use Django's validation utility
            except DjangoValidationError as e:
                raise serializers.ValidationError({"password": e.messages})  # Convert to DRF's ValidationError

        user = User.objects.create(address=address, **validated_data)

        if password:
            user.set_password(password)
            user.save()

        # Automatically add the user's email to AssociatedEmail
        request = self.context.get('request')
        AssociatedEmail.objects.create(
            user=user,
            email=user.email,
            added_by=user
        )
        return user

    def update(self, instance, validated_data):
        """Update a user."""
        password = validated_data.pop('password', None)

        if 'address' in validated_data:  # check if address is in validated_data
            address_data = validated_data.pop('address')
            if address_data is not None:  # address_data is not None, then update Address instance
                address = instance.address
                address.line1 = address_data.get('line1', address.line1)
                address.line2 = address_data.get('line2', address.line2)
                address.town_city = address_data.get('town_city', address.town_city)
                address.county = address_data.get('county', address.county)
                address.eircode = address_data.get('eircode', address.eircode)
                address.save()
            else:  # address_data is None, then do not change address
                pass

        phone_number = validated_data.pop('phone_number', None)
        if phone_number and not phone_number.startswith('+'):
            phone_number = '+353' + phone_number.lstrip('0')
        instance.phone_number = phone_number

        # Check if email is updated and update in AssociatedEmail
        new_email = validated_data.get('email', None)
        if new_email and new_email != instance.email:
            request = self.context.get('request')

            # Update the email in AssociatedEmail or create a new one if it doesn't exist
            associated_email, created = AssociatedEmail.objects.get_or_create(
                user=instance,
                email=new_email,
                defaults={'added_by': request.user if request else None}
            )
            if not created:
                associated_email.added_by = request.user if request else None
                associated_email.save()

        user = super().update(instance, validated_data)

        return user

    def validate_phone_number(self, value):
        """Validate Irish phone numbers."""
        pattern = r"^((0((1)|[2-9]\d))\d{5,7}|(083|085|086|087|089)\d{7})$"
        if not re.match(pattern, value):
            raise ValidationError(
                "Invalid Irish phone number. "
                "Mobile numbers must follow the format 083/085/086/087/089 followed by 7 digits. "
                "Landline numbers must start with area codes 01 to 095 followed by 5 to 7 digits. "
                "Please do not include the country code (+353)."
            )
        return value


class UpdatePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True)

    def validate_new_password(self, value):
        """
        Validate the new password using Django's password validation.
        """
        user = self.context['request'].user  # Get the currently authenticated user
        try:
            validate_user_password(value, user=user)  # Pass the user for similarity checks
        except DjangoValidationError as e:
            raise serializers.ValidationError(e.messages)  # Convert to DRF ValidationError
        return value


class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        # Standard validation to get the token data
        data = super().validate(attrs)

        # Check if the user is active
        if not self.user.is_active:
            raise serializers.ValidationError(
                _("User account is disabled or inactive."),
                code='authorization'
            )

        # Include additional user data in the response
        data.update({'user': self.user.email})
        return data


# Serializer for Forgot Password Request
class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()


# Serializer for Reset Password Request
class ResetPasswordSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True)

    def validate_password(self, value):
        """
        Validate the password using Django's built-in validators.
        """
        try:
            validate_user_password(value)  # Validate the password
        except DjangoValidationError as e:
            raise serializers.ValidationError(e.messages)  # Convert errors to DRF ValidationError
        return value
