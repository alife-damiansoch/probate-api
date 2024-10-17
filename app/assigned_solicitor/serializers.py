from rest_framework import serializers
from core.models import Solicitor, AssociatedEmail


class AssignedSolicitorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Solicitor
        fields = ['id', 'user', 'title', 'first_name', 'last_name', 'own_email', 'own_phone_number']
        read_only_fields = ['id', 'user']

    def create(self, validated_data):
        # Create the solicitor
        solicitor = super().create(validated_data)

        # Add solicitor's own_email to AssociatedEmail if provided
        own_email = validated_data.get('own_email')
        if own_email:
            request = self.context.get('request', None)
            AssociatedEmail.objects.create(
                user=solicitor.user,  # Assuming solicitor.user is linked to the firm (User)
                email=own_email,
                added_by=request.user if request and request.user.is_authenticated else None
            )
        return solicitor

    def update(self, instance, validated_data):
        # Store the original email for comparison
        old_email = instance.own_email
        # Update the solicitor
        solicitor = super().update(instance, validated_data)

        # Get the new email
        new_own_email = validated_data.get('own_email')

        # Check if the email has changed
        if new_own_email and new_own_email != old_email:
            request = self.context.get('request', None)

            # Update or create an entry in AssociatedEmail for the new email
            associated_email, created = AssociatedEmail.objects.get_or_create(
                user=solicitor.user,  # Assuming solicitor.user is linked to the firm (User)
                email=new_own_email,
                defaults={'added_by': request.user if request and request.user.is_authenticated else None}
            )
            if not created:
                # If it already exists, update who added it
                associated_email.added_by = request.user if request and request.user.is_authenticated else None
                associated_email.save()

        return solicitor
