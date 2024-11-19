"""
Django admin customization.
"""

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django import forms
from django.utils import timezone
from django.core.exceptions import ValidationError

from rangefilter.filters import DateRangeFilter

from django.utils.translation import gettext_lazy as _
from django.utils.html import format_html
from django.urls import reverse

from core import models
from core.models import LoanExtension, Transaction, Document, Solicitor, SignedDocumentLog, Assignment, EmailLog, \
    AssociatedEmail, UserEmailLog, CommitteeApproval

from rest_framework.authtoken.models import Token

from auditlog.models import LogEntry


class AssignedSolicitorInline(admin.TabularInline):
    """Inline admin class for AssignedSolicitor"""

    model = Solicitor
    extra = 1  # Number of empty forms to display; can be adjusted
    readonly_fields = ['user']  # Prevents user field from being editable in the inline form

    def get_queryset(self, request):
        """Customize the queryset to display only solicitors belonging to the user"""
        qs = super().get_queryset(request)
        return qs.select_related('user')


class UserAdmin(BaseUserAdmin):
    """Define admin pages for users"""

    ordering = ["id"]
    list_display = ["email", "name"]
    actions = ['delete_selected_with_tokens']

    filter_horizontal = ('teams',)  # This adds a more user-friendly interface for selecting teams

    def delete_selected_with_tokens(self, request, queryset):
        for obj in queryset:
            # Delete related tokens of the user
            Token.objects.filter(user=obj).delete()  # delete relevant tokens here
            obj.delete()

    delete_selected_with_tokens.short_description = 'Delete selected users with related tokens'

    fieldsets = (
        (None, {"fields": ("email", "password", "teams", "phone_number", "name", "address")}),
        (
            _("Permissions"),
            {"fields": (
                "is_active",
                "is_staff",
                "is_superuser",
            )}
        ),
        (
            _("Important dates"),
            {"fields": (
                "last_login",
            )}
        ),
    )
    readonly_fields = ["last_login"]

    search_fields = ['email', ]

    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": (
                "email",
                "password1",
                "password2",
                "name",
                "teams",
                "is_active",
                "is_staff",
                "is_superuser",
                "phone_number",
                "address"
            )
        }),
    )

    def get_inline_instances(self, request, obj=None):
        """Show the AssignedSolicitor inline only for non-staff users."""
        inline_instances = []

        # Check if the user is non-staff before adding the inline
        if obj and not obj.is_staff:
            inline_instances = [AssignedSolicitorInline(self.model, self.admin_site)]

        return inline_instances


class EstateInline(admin.TabularInline):
    model = models.Estate
    extra = 0


class ExpenseInline(admin.TabularInline):
    model = models.Expense
    extra = 0


class ApplicantInline(admin.StackedInline):
    model = models.Applicant
    extra = 0


class DocumentInline(admin.StackedInline):
    model = models.Document
    extra = 0
    max_num = 0  # Disallows adding new Document instances
    readonly_fields = ['id', 'document', 'original_name']


class ApplicationForm(forms.ModelForm):
    user = forms.ModelChoiceField(
        queryset=get_user_model().objects.filter(is_staff=False)
    )
    assigned_to = forms.ModelChoiceField(
        queryset=get_user_model().objects.filter(is_staff=True), required=False
    )

    class Meta:
        model = models.Application
        fields = '__all__'


from django.contrib import admin
from django.utils.translation import gettext_lazy as _


class ApplicationAdmin(admin.ModelAdmin):
    ordering = ["id"]
    form = ApplicationForm
    inlines = [ApplicantInline, EstateInline, ExpenseInline, DocumentInline]

    fieldsets = (
        (None,
         {"fields": ("amount", "term", "user", "solicitor", "deceased", "dispute", "assigned_to", "last_updated_by",)}),
        (_("Details"), {"fields": (
            "approved", "is_rejected", "rejected_reason", "rejected_date", "undertaking_ready", "loan_agreement_ready",
            "value_of_the_estate_after_expenses")}),
    )

    readonly_fields = (
        'id', 'last_updated_by', 'deceased_full_name', 'dispute_details', 'date_submitted', 'deceased', 'dispute',
        'user', "rejected_date", "undertaking_ready", "loan_agreement_ready", "value_of_the_estate_after_expenses")

    search_fields = ["id", ]
    list_display = ("id", "user", "solicitor", "assigned_to", "deceased_full_name", "dispute_details",
                    "value_of_the_estate_after_expenses", "undertaking_ready", "loan_agreement_ready")

    def deceased_full_name(self, obj):
        if obj.deceased:
            return f"{obj.deceased.first_name} {obj.deceased.last_name}"
        return "No deceased attached to this application"

    def dispute_details(self, obj):
        if obj.dispute:
            return obj.dispute.details
        return "No dispute attached to this application"

    deceased_full_name.short_description = 'Deceased'
    dispute_details.short_description = 'Dispute'

    def save_model(self, request, obj, form, change):
        if not obj.pk:  # If the object is being created
            obj.user = request.user
        else:  # Object is being updated
            obj.last_updated_by = request.user
        super().save_model(request, obj, form, change)


class TransactionInline(admin.TabularInline):
    model = Transaction
    extra = 0  # Number of extra forms to display
    readonly_fields = ['created_by']


class LoanExtensionInline(admin.TabularInline):
    model = LoanExtension
    extra = 0
    readonly_fields = ['created_by', 'created_date']


class LoanAdmin(admin.ModelAdmin):
    fieldsets = (
        (_("Loan Details"), {
            "fields": (
                "application", "amount_agreed", 'fee_agreed', "term_agreed", "approved_date",
                "approved_by", "last_updated_by", "needs_committee_approval", "is_committee_approved",
            )
        }),
        (_("Settled / Paid_out Info"), {
            "fields": (
                "is_paid_out", "paid_out_date", "pay_out_reference_number", "is_settled", "settled_date",
            ),
        }),
        (_("Committee Approval Status"), {
            "fields": ("committee_approvements_status",),  # Display committee approval status
        }),
        (_("Read-only Info"), {
            "fields": ("maturity_date", "current_balance", "amount_paid", "extension_fees_total",),
        }),
    )

    readonly_fields = (
        'application', "maturity_date", "current_balance", "amount_paid", "last_updated_by", "approved_by",
        "extension_fees_total", "committee_approvements_status",
    )
    ordering = ["id"]
    inlines = [TransactionInline, LoanExtensionInline]
    list_display = [
        "id", "application", "amount_agreed", "term_agreed", "approved_by", "last_updated_by",
        "is_paid_out", "needs_committee_approval", "is_committee_approved",  # Added new fields to list_display
    ]

    def save_model(self, request, obj, form, change):
        if not obj.pk:  # If object is being created
            obj.approved_by = request.user
        obj.last_updated_by = request.user  # Object is being updated
        super().save_model(request, obj, form, change)

    def save_formset(self, request, form, formset, change):
        if formset.model == models.Transaction:
            instances = formset.save(commit=False)
            for instance in instances:
                if not instance.pk:  # If object is being created
                    instance.created_by = request.user
                instance.save()
        elif formset.model == models.LoanExtension:
            instances = formset.save(commit=False)
            for instance in instances:
                if not instance.pk:  # If object is being created
                    instance.created_by = request.user
                    instance.created_date = timezone.now()
                instance.save()
        formset.save_m2m()  # Save many-to-many and many-to-one relationship fields


class EventsAdmin(admin.ModelAdmin):
    ordering = ["-created_at"]
    list_display = ["request_id", "path", 'response_status', 'response', 'created_at', 'user', 'is_error']
    list_filter = (
        ('created_at', DateRangeFilter), 'response_status', 'is_error'
    )
    readonly_fields = [f.name for f in models.Event._meta.get_fields()]


class DocumentAdmin(admin.ModelAdmin):
    search_fields = ['original_name', 'application__id']


class CustomLogEntryAdmin(admin.ModelAdmin):
    # Adjust search_fields as per your model relations
    search_fields = ['object_pk', 'actor__email']


class SignedDocumentLogAdmin(admin.ModelAdmin):
    """Admin configuration for the SignedDocumentLog model with field grouping."""

    # Define fieldsets for grouping fields into sections
    fieldsets = (
        ("User and Application Details", {
            'fields': (
                'user',
                'application',
                'timestamp',
                'ip_address',
            )
        }),
        ("Document Data", {
            'fields': (
                'signature_hash',
                'file_path',
                'signing_user_email',
                'solicitor_full_name',
                'confirmation_message',
                'confirmation_checked_by_user',
            )
        }),
        ("Geolocation Data", {
            'fields': (
                'country',
                'country_code',
                'region',
                'region_name',
                'city',
                'zip',
                'latitude',
                'longitude',
                'timezone',
                'isp',
                'org',
                'as_number',
            )
        }),
        ("Proxy Data", {
            'fields': (
                'is_proxy',
                'type',
                'proxy_provider',
            )
        }),
        ("Device Information", {  # New section for device information
            'fields': (
                'device_user_agent',
                'device_browser_name',
                'device_browser_version',
                'device_os_name',
                'device_os_version',
                'device_cpu_architecture',
                'device_type',
                'device_model',
                'device_vendor',
                'device_screen_resolution',
            )
        }),
        ("Signature Image Data", {  # Section for displaying Base64 value
            'fields': ('display_signature_image_base64',)  # Use the custom display method
        }),
    )

    # Specify the fields to display in the list view
    list_display = (
        'id',
        'user',
        'application',
        'timestamp',
        'ip_address',

        # Document Data
        'signature_hash',
        'file_path',
        'signing_user_email',
        'solicitor_full_name',
        'confirmation_message',
        'confirmation_checked_by_user',

        # Geolocation Data
        'country',
        'country_code',
        'region',
        'region_name',
        'city',
        'zip',
        'latitude',
        'longitude',
        'timezone',
        'isp',
        'org',
        'as_number',

        # Proxy Data
        'is_proxy',
        'type',
        'proxy_provider',

        # Device Information
        'device_browser_name',
        'device_browser_version',
        'device_os_name',
        'device_os_version',
        'device_type',
        'device_model',
        'device_vendor',
    )

    # Custom method to display the full `signature_image_base64` in the detail view
    def display_signature_image_base64(self, obj):
        if obj.signature_image_base64:
            # Display the Base64 string in a scrollable text area
            return format_html(
                f'<textarea rows="20" cols="80" readonly style="white-space: pre-wrap;">{obj.signature_image_base64}</textarea>'
            )
        else:
            return format_html('<span style="color: gray;">No Signature Image Available</span>')

    display_signature_image_base64.short_description = 'Signature Image Base64 (Full)'

    # Make all fields read-only
    readonly_fields = (
        'user',
        'application',
        'timestamp',
        'ip_address',
        'signature_hash',
        'file_path',
        'signing_user_email',
        'solicitor_full_name',
        'confirmation_message',
        'confirmation_checked_by_user',
        'country',
        'country_code',
        'region',
        'region_name',
        'city',
        'zip',
        'latitude',
        'longitude',
        'timezone',
        'isp',
        'org',
        'as_number',
        'is_proxy',
        'type',
        'proxy_provider',
        'device_user_agent',
        'device_browser_name',
        'device_browser_version',
        'device_os_name',
        'device_os_version',
        'device_cpu_architecture',
        'device_type',
        'device_model',
        'device_vendor',
        'device_screen_resolution',
        'display_signature_image_base64',  # Use the custom method in read-only fields
    )

    # Add search fields for easier lookup by specific attributes
    search_fields = (
        'solicitor_full_name',
        'signing_user_email',
        'signature_hash',
        'application__id',
    )

    # Set default ordering
    ordering = ('-timestamp',)


class AssignmentAdmin(admin.ModelAdmin):
    """Admin configuration for the Assignment model."""

    list_display = (
        'staff_user',  # Corrected to reference the actual field name
        'agency_user',  # Corrected to reference the actual field name
        'assigned_at',  # Assuming you have an assigned_at field in the model
    )

    list_filter = (
        'staff_user',  # Corrected to reference the actual field name
        'agency_user',  # Corrected to reference the actual field name
    )

    search_fields = (
        'staff_user__name',  # Adding staff_user and agency_user fields for better search
        'agency_user__name',
    )

    ordering = ('-assigned_at',)  # Assuming you have an 'assigned_at' field to order by


class EmailLogAdmin(admin.ModelAdmin):
    # Displaying the fields in the list view
    list_display = ('subject', 'sender', 'recipient', 'application', 'solicitor_firm', 'created_at', 'is_sent')

    # Adding search functionality for specific fields
    search_fields = (
        'subject', 'sender', 'recipient', 'message', 'created_at', 'application__id', 'solicitor_firm__email')

    # Enabling filtering by fields
    list_filter = ('is_sent', 'created_at', 'solicitor_firm', 'application')

    # Enabling ordering
    ordering = ('-created_at',)


admin.site.unregister(LogEntry)
admin.site.register(LogEntry, CustomLogEntryAdmin)

admin.site.register(models.User, UserAdmin)
admin.site.register(models.Team)
admin.site.register(models.Address)
admin.site.register(models.Application, ApplicationAdmin)
admin.site.register(models.Deceased)
admin.site.register(models.Estate)
admin.site.register(models.Dispute)
admin.site.register(models.Event, EventsAdmin)
admin.site.register(models.Loan, LoanAdmin)

admin.site.register(models.Applicant)

admin.site.register(models.Notification)
admin.site.register(models.Solicitor)

admin.site.register(Document, DocumentAdmin)

admin.site.register(SignedDocumentLog, SignedDocumentLogAdmin)
admin.site.register(Assignment, AssignmentAdmin)
admin.site.register(EmailLog, EmailLogAdmin)
admin.site.register(UserEmailLog, EmailLogAdmin)


@admin.register(AssociatedEmail)
class AssociatedEmailAdmin(admin.ModelAdmin):
    search_fields = ['user__email']  # Enables search by user email


@admin.register(CommitteeApproval)
class CommitteeApprovalAdmin(admin.ModelAdmin):
    list_display = ('loan', 'get_application_link', 'member', 'approved', 'rejection_reason', 'decision_date')
    list_filter = ('approved',)  # Filter options for approved status
    search_fields = ('loan__id', 'application__id',)  # Enable search by loan ID
    ordering = ['loan', 'member']  # Sort by loan and member for better readability
    readonly_fields = ('decision_date', 'loan', 'member', 'application')  # Make fields read-only

    fieldsets = (
        (None, {
            'fields': ('loan', 'application', 'member', 'approved', 'rejection_reason')
        }),
        ('Decision Info', {
            'fields': ('decision_date',),
        }),
    )

    def get_application_link(self, obj):
        if obj.application:
            # Create a clickable link to the application object in the admin
            url = reverse('admin:core_application_change', args=[obj.application.id])
            return format_html('<a href="{}">{}</a>', url, obj.application)
        return "-"

    get_application_link.short_description = 'Application'  # Rename the column header to 'Application'

    # Override save_model to provide custom messaging if needed
    def save_model(self, request, obj, form, change):
        if not obj.approved and not obj.rejection_reason:
            self.message_user(request, "Please provide a rejection reason when rejecting.", level='error')
        super().save_model(request, obj, form, change)
