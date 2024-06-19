"""Serializers for the User Api view"""

from rest_framework import serializers
from django.contrib.auth import (get_user_model, authenticate, )
from django.utils.translation import gettext as _


class UserListSerializer(serializers.ModelSerializer):
    """Serializer for listing users, returns only id and email fields"""

    class Meta:
        model = get_user_model()
        fields = ['id', 'email']
        read_only_fields = ['id', 'email']


class UserSerializer(serializers.ModelSerializer):
    """Serializer for the User model"""

    class Meta:
        model = get_user_model()
        fields = ['id', 'email', 'password', 'name', 'phone_number', 'address', 'team', 'is_active', 'is_staff',
                  'is_superuser']
        extra_kwargs = {'password': {'write_only': True, 'min_length': 5}}
        read_only_fields = ('id', 'is_active', 'is_staff', 'is_superuser', 'team')

    def create(self, validated_data):
        """Create a new user with encrypted password and return it"""
        password = validated_data.pop('password', None)
        address = validated_data.pop('address', None)

        user = self.Meta.model(**validated_data)
        user.address = address
        user.set_password(password)
        # user is saved after password is set
        user.save()
        return user

    def update(self, instance, validated_data):
        """Update a user."""
        password = validated_data.pop('password', None)
        address = validated_data.pop('address', None)

        user = super().update(instance, validated_data)
        user.address = address

        if password:
            user.set_password(password)
            user.save()

        return user


class AuthTokenSerializer(serializers.Serializer):
    """Serializer for the User auth token"""
    email = serializers.EmailField()
    password = serializers.CharField(
        style={'input_type': 'password'},
        trim_whitespace=False
    )

    def validate(self, attrs):
        """Validate and authenticate the user."""
        email = attrs.get('email')
        password = attrs.get('password')
        user = authenticate(request=self.context.get('request'), username=email, password=password)
        if not user:
            msg = _('Unable to authenticate with provided credentials')
            raise serializers.ValidationError(msg, code='authentication')
        attrs['user'] = user
        return attrs
