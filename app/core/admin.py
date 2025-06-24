"""
Django admin customization.
"""
from cryptography.fernet import Fernet
from django.contrib import admin
from django.contrib.admin import SimpleListFilter
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django import forms
from django.forms import TextInput
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.utils.safestring import mark_safe

from rangefilter.filters import DateRangeFilter

from django.utils.translation import gettext_lazy as _
from django.utils.html import format_html
from django.urls import reverse

from app import settings
from core import models
from core.models import LoanExtension, Transaction, Document, Solicitor, SignedDocumentLog, Assignment, EmailLog, \
    AssociatedEmail, UserEmailLog, CommitteeApproval, Team, OTP, AuthenticatorSecret, FrontendAPIKey, \
    RealAndLeaseholdProperty, \
    HouseholdContents, CarsBoats, BusinessFarming, BusinessOther, \
    UnpaidPurchaseMoney, FinancialAsset, LifeInsurance, DebtOwed, SecuritiesQuoted, \
    SecuritiesUnquoted, OtherProperty, IrishDebt, ApplicationProcessingStatus, InternalFile

from rest_framework.authtoken.models import Token

from auditlog.models import LogEntry

from document_emails.models import EmailDeliveryLog, EmailDocument, EmailCommunication
from document_requirements.models import ApplicationDocumentRequirement, DocumentType
from finance_checklist.models import LoanChecklistSubmission, FinanceChecklistItem, LoanChecklistItemCheck, \
    ChecklistConfiguration
from loanbook.models import LoanBook


class AssignedSolicitorInline(admin.TabularInline):
    """Inline admin class for AssignedSolicitor"""

    model = Solicitor
    extra = 1  # Number of empty forms to display; can be adjusted
    readonly_fields = ['user']  # Prevents user field from being editable in the inline form

    def get_queryset(self, request):
        """Customize the queryset to display only solicitors belonging to the user"""
        qs = super().get_queryset(request)
        return qs.select_related('user')


class TeamFilter(SimpleListFilter):
    title = 'team'  # The title displayed in the admin filter sidebar
    parameter_name = 'team'  # The query parameter used in the URL

    def lookups(self, request, model_admin):
        """Return a list of tuples (value, display_name) for filter options."""
        teams = Team.objects.all()
        return [(team.id, team.name) for team in teams]

    def queryset(self, request, queryset):
        """Filter the queryset based on the selected value."""
        if self.value():
            return queryset.filter(teams__id=self.value())
        return queryset


class UserAdmin(BaseUserAdmin):
    """Define admin pages for users"""

    ordering = ["id"]
    list_display = ["email", "name", "country", "preferred_auth_method", "get_teams"]  # Added preferred_auth_method
    actions = ['delete_selected_with_tokens']

    filter_horizontal = ('teams',)  # User-friendly interface for selecting teams

    # Custom filters
    list_filter = ['is_staff', 'is_superuser', 'is_active', TeamFilter]

    def delete_selected_with_tokens(self, request, queryset):
        for obj in queryset:
            # Delete related tokens of the user
            Token.objects.filter(user=obj).delete()
            obj.delete()

    delete_selected_with_tokens.short_description = 'Delete selected users with related tokens'

    # Add the preferred_auth_method field to fieldsets
    fieldsets = (
        (None, {
            "fields": (
                "email", "password", "teams", "phone_number", "name", "address", "country", "preferred_auth_method")
        }),
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
        (
            "Activation",
            {"fields": ("activation_token",)},  # Add activation token field
        ),
    )
    readonly_fields = ["last_login", "activation_token"]  # Make activation_token read-only

    search_fields = ['email', ]

    # Add preferred_auth_method to the add_fieldsets
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
                "address",
                "country",
                "preferred_auth_method",
            )
        }),
    )

    def get_form(self, request, obj=None, **kwargs):
        """Customize the form to completely disable the teams field for non-staff users."""
        form = super().get_form(request, obj, **kwargs)

        # Check if the teams field exists before making changes
        if 'teams' in form.base_fields:
            if obj and not obj.is_staff:
                # Replace the widget with a non-interactive one
                form.base_fields['teams'].widget = TextInput(attrs={
                    'disabled': 'disabled',
                    'style': 'pointer-events: none; background-color: #e9ecef;',  # Optional styling for clarity
                })

        return form

    def get_teams(self, obj):
        """
        Retrieve and format the teams for display in the admin list.
        """
        return ", ".join([team.name for team in obj.teams.all()])

    get_teams.short_description = "Teams"  # Set column header in admin

    def get_inline_instances(self, request, obj=None):
        """Show the AssignedSolicitor inline only for non-staff users."""
        inline_instances = []

        # Check if the user is non-staff before adding the inline
        if obj and not obj.is_staff:
            inline_instances = [AssignedSolicitorInline(self.model, self.admin_site)]

        return inline_instances


class RealAndLeaseholdInline(admin.TabularInline):
    model = RealAndLeaseholdProperty
    extra = 0


class HouseholdContentsInline(admin.TabularInline):
    model = HouseholdContents
    extra = 0


class CarsBoatsInline(admin.TabularInline):
    model = CarsBoats
    extra = 0


class BusinessFarmingInline(admin.TabularInline):
    model = BusinessFarming
    extra = 0


class BusinessOtherInline(admin.TabularInline):
    model = BusinessOther
    extra = 0


class UnpaidPurchaseMoneyInline(admin.TabularInline):
    model = UnpaidPurchaseMoney
    extra = 0


class FinancialAssetInline(admin.TabularInline):
    model = FinancialAsset
    extra = 0


class LifeInsuranceInline(admin.TabularInline):
    model = LifeInsurance
    extra = 0


class DebtOwedInline(admin.TabularInline):
    model = DebtOwed
    extra = 0


class SecuritiesQuotedInline(admin.TabularInline):
    model = SecuritiesQuoted
    extra = 0


class SecuritiesUnquotedInline(admin.TabularInline):
    model = SecuritiesUnquoted
    extra = 0


class OtherPropertyInline(admin.TabularInline):
    model = OtherProperty
    extra = 0


class IrishDebtInline(admin.TabularInline):
    model = IrishDebt
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


class ApplicationProcessingStatusInline(admin.StackedInline):
    model = ApplicationProcessingStatus
    extra = 0
    max_num = 1
    can_delete = False

    fields = (
        'application_details_completed_confirmed',
        'solicitor_preferred_aml_method',
        'last_updated_by',
        'date_updated'
    )

    readonly_fields = ('last_updated_by', 'date_updated')

    def save_model(self, request, obj, form, change):
        if change:
            obj.last_updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(models.Application)
class ApplicationAdmin(admin.ModelAdmin):
    ordering = ["id"]
    form = ApplicationForm
    inlines = [
        ApplicationProcessingStatusInline,  # Add this at the top
        ApplicantInline,
        ExpenseInline,
        DocumentInline,

        # New split estate inlines
        RealAndLeaseholdInline,
        HouseholdContentsInline,
        CarsBoatsInline,
        BusinessFarmingInline,
        BusinessOtherInline,
        UnpaidPurchaseMoneyInline,
        FinancialAssetInline,
        LifeInsuranceInline,
        DebtOwedInline,
        SecuritiesQuotedInline,
        SecuritiesUnquotedInline,
        OtherPropertyInline,
        IrishDebtInline,
    ]

    fieldsets = (
        (None, {
            "fields": (
                "amount", "term", "user", "solicitor", "deceased", "dispute", "assigned_to", "last_updated_by",
            )
        }),
        (_("Details"), {
            "fields": (
                "was_will_prepared_by_solicitor",
                "is_new", "approved", "is_rejected", "rejected_reason", "rejected_date",
                "undertaking_ready", "loan_agreement_ready", "value_of_the_estate_after_expenses"
            )
        }),
    )

    readonly_fields = (
        'id', 'last_updated_by', 'deceased_full_name', 'dispute_details', 'date_submitted', 'deceased', 'dispute',
        'user', "rejected_date", "undertaking_ready", "loan_agreement_ready", "value_of_the_estate_after_expenses")

    search_fields = ["id", ]
    list_display = ("id", "user", "solicitor", "assigned_to", "deceased_full_name", "dispute_details",
                    "value_of_the_estate_after_expenses", "undertaking_ready", "loan_agreement_ready",
                    "processing_status_confirmed", "processing_aml_method")  # Added processing status columns

    # Add methods to display processing status in list view
    def processing_status_confirmed(self, obj):
        try:
            return obj.processing_status.application_details_completed_confirmed
        except ApplicationProcessingStatus.DoesNotExist:
            return False

    processing_status_confirmed.boolean = True
    processing_status_confirmed.short_description = 'Status Confirmed'

    def processing_aml_method(self, obj):
        try:
            return obj.processing_status.solicitor_preferred_aml_method or '-'
        except ApplicationProcessingStatus.DoesNotExist:
            return '-'

    processing_aml_method.short_description = 'AML Method'

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
        if not obj.pk:
            obj.user = request.user
        else:
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

    # List Display
    list_display = [
        "id", "application_id", "amount_agreed", "term_agreed", "get_approved_by_email",
        "get_last_updated_by_email", "is_paid_out", "needs_committee_approval",
        "is_committee_approved", "is_settled",
    ]

    # Search and Filter
    search_fields = ["application__id"]  # Enable searching by application.id
    list_filter = [
        "is_settled", "needs_committee_approval", "is_committee_approved", "is_paid_out",
    ]  # Add filtering options for the specified fields

    # Custom method to display approved_by.email
    def get_approved_by_email(self, obj):
        return obj.approved_by.email if obj.approved_by else None

    get_approved_by_email.short_description = "Approved By Email"

    # Custom method to display last_updated_by.email
    def get_last_updated_by_email(self, obj):
        return obj.last_updated_by.email if obj.last_updated_by else None

    get_last_updated_by_email.short_description = "Last Updated By Email"

    # Save methods
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


class NotificationAdmin(admin.ModelAdmin):
    list_display = ('id', 'recipient_email', 'text_preview', 'application_id', 'seen', 'timestamp', 'created_by_email')
    list_filter = ('seen', 'timestamp')  # Add filters for easier navigation
    search_fields = (
        'recipient__email', 'text', 'application__id')  # Enable searching by Application ID, recipient email, and text

    def recipient_email(self, obj):
        return obj.recipient.email if obj.recipient else 'No recipient'

    recipient_email.short_description = 'Recipient Email'

    def text_preview(self, obj):
        return obj.text[:50]  # Show a preview of the text (first 50 characters)

    text_preview.short_description = 'Text Preview'

    def application_id(self, obj):
        return obj.application.id if obj.application else 'No application'

    application_id.short_description = 'Application ID'

    def created_by_email(self, obj):
        return obj.created_by.email if obj.created_by else 'No creator'

    created_by_email.short_description = 'Created By'


class TeamAdmin(admin.ModelAdmin):
    list_display = ('name', 'note')

    def note(self, obj):
        return format_html(
            "<i>Note: Teams following the <b>countryCode_team</b> naming format (e.g., <b>ie_team</b>, <b>uk_team</b>) are exclusively reserved for assigning agents to work with users from specific countries. This format should not be used for any other purposes.</i>"
        )

    note.short_description = "Important Information"


class ApplicantAdmin(admin.ModelAdmin):
    list_display = ('first_name', 'last_name', 'application', 'decrypted_pps_display')
    search_fields = ('first_name', 'last_name', 'application__id')  # Standard search fields

    def decrypted_pps_display(self, obj):
        """Display the decrypted PPS number in the admin list view."""
        try:
            return obj.decrypted_pps
        except Exception:
            return "Error decrypting"

    decrypted_pps_display.short_description = "Decrypted PPS"

    def get_search_results(self, request, queryset, search_term):
        """Customize search to include decrypted PPS."""
        # Start with the default search behavior
        queryset, use_distinct = super().get_search_results(request, queryset, search_term)

        # Add custom filtering for decrypted PPS
        matching_ids = []
        for applicant in models.Applicant.objects.all():
            try:
                # Check if decrypted PPS matches the search term
                if search_term in (applicant.decrypted_pps or ''):
                    matching_ids.append(applicant.id)
            except Exception:
                continue  # Ignore errors during decryption

        # Include the matching applicants in the queryset
        if matching_ids:
            queryset |= models.Applicant.objects.filter(id__in=matching_ids)

        return queryset, use_distinct


admin.site.unregister(LogEntry)
admin.site.register(LogEntry, CustomLogEntryAdmin)

admin.site.register(models.User, UserAdmin)
admin.site.register(models.Team, TeamAdmin)
admin.site.register(models.Address)

admin.site.register(models.Deceased)

admin.site.register(models.Dispute)
admin.site.register(models.Event, EventsAdmin)
admin.site.register(models.Loan, LoanAdmin)

admin.site.register(models.Applicant, ApplicantAdmin)

admin.site.register(models.Notification, NotificationAdmin)
admin.site.register(models.Solicitor)

admin.site.register(Document, DocumentAdmin)

admin.site.register(SignedDocumentLog, SignedDocumentLogAdmin)
admin.site.register(Assignment, AssignmentAdmin)
admin.site.register(EmailLog, EmailLogAdmin)
admin.site.register(UserEmailLog, EmailLogAdmin)
admin.site.register(FrontendAPIKey)


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


@admin.register(OTP)
class OTPAdmin(admin.ModelAdmin):
    list_display = ('email', 'code', 'created_at', 'is_valid')  # Columns to display
    readonly_fields = ('code',)  # Make OTP code read-only
    search_fields = ('email',)  # Search by email

    def is_valid(self, obj):
        return obj.is_valid()

    is_valid.boolean = True  # Display as a boolean icon
    is_valid.short_description = "Valid?"  # Custom column header


@admin.register(AuthenticatorSecret)
class AuthenticatorSecretAdmin(admin.ModelAdmin):
    list_display = ('user', 'user_email', 'created_at')  # Columns to display
    readonly_fields = ('secret',)  # Make secret read-only
    search_fields = ('user__email',)  # Search by user's email

    def user_email(self, obj):
        return obj.user.email  # Display user's email

    user_email.short_description = "User Email"  # Custom column header


@admin.register(DocumentType)
class DocumentTypeAdmin(admin.ModelAdmin):
    list_display = [
        'name',
        'signature_required',
        'who_needs_to_sign',
        'order',
        'is_active',
        'usage_count',
        'created_at'
    ]
    list_filter = ['signature_required', 'who_needs_to_sign', 'is_active', 'created_at']
    search_fields = ['name', 'description']
    list_editable = ['order', 'is_active']
    ordering = ['order', 'name']
    readonly_fields = ['created_at', 'updated_at', 'usage_count']

    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'order', 'is_active')
        }),
        ('Signature Requirements', {
            'fields': ('signature_required', 'who_needs_to_sign'),
            'description': 'Configure if this document type requires signatures'
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at', 'usage_count'),
            'classes': ('collapse',)
        }),
    )

    def usage_count(self, obj):
        count = ApplicationDocumentRequirement.objects.filter(document_type=obj).count()
        return format_html(
            '<span style="color: {};">{} applications</span>',
            '#28a745' if count > 0 else '#6c757d',
            count
        )

    usage_count.short_description = "Usage"

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('applicationdocumentrequirement_set')


@admin.register(ApplicationDocumentRequirement)
class ApplicationDocumentRequirementAdmin(admin.ModelAdmin):
    list_display = [
        'application_link',
        'document_type',
        'is_uploaded_display',
        'created_at',
        'created_by'
    ]
    list_filter = [
        'document_type',
        'created_at',
        'document_type__signature_required'
    ]
    search_fields = [
        'application__id',
        'document_type__name',
        'created_by__email'
    ]
    readonly_fields = ['created_at', 'is_uploaded_display']
    raw_id_fields = ['application', 'created_by']

    fieldsets = (
        ('Requirement Details', {
            'fields': ('application', 'document_type')
        }),
        ('Status', {
            'fields': ('is_uploaded_display',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'created_by'),
            'classes': ('collapse',)
        }),
    )

    def application_link(self, obj):
        return format_html(
            '<a href="/admin/core/application/{}/change/">#{}</a>',
            obj.application.id,
            obj.application.id
        )

    application_link.short_description = "Application"
    application_link.admin_order_field = 'application__id'

    def is_uploaded_display(self, obj):
        if obj.is_uploaded:
            return format_html(
                '<span style="color: #28a745; font-weight: bold;">✓ Uploaded</span>'
            )
        else:
            return format_html(
                '<span style="color: #dc3545; font-weight: bold;">✗ Missing</span>'
            )

    is_uploaded_display.short_description = "Upload Status"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'application', 'document_type', 'created_by'
        )


@admin.register(InternalFile)
class InternalFileAdmin(admin.ModelAdmin):
    list_display = ['title', 'application', 'uploaded_by', 'created_at', 'is_active']
    list_filter = ['is_active', 'created_at', 'uploaded_by']
    search_fields = ['title', 'description', 'application__id']
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        (None, {
            'fields': ('title', 'description', 'file', 'application', 'is_active')
        }),
        ('Metadata', {
            'fields': ('uploaded_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('application', 'uploaded_by')


@admin.register(FinanceChecklistItem)
class FinanceChecklistItemAdmin(admin.ModelAdmin):
    list_display = ['title', 'is_active', 'order', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['title', 'description']
    list_editable = ['is_active', 'order']
    list_per_page = 50
    ordering = ['order', 'title']

    fieldsets = (
        (None, {
            'fields': ('title', 'description', 'is_active', 'order')
        }),
    )


@admin.register(ChecklistConfiguration)
class ChecklistConfigurationAdmin(admin.ModelAdmin):
    list_display = ['required_approvers', 'is_active', 'created_at', 'updated_at']
    list_filter = ['is_active', 'created_at']

    fieldsets = (
        (None, {
            'fields': ('required_approvers', 'is_active'),
            'description': 'Configure how many staff users must complete the checklist for each loan.'
        }),
    )

    def has_add_permission(self, request):
        # Only allow adding if no active configuration exists
        return not ChecklistConfiguration.objects.filter(is_active=True).exists()


class LoanChecklistItemCheckInline(admin.TabularInline):
    model = LoanChecklistItemCheck
    extra = 0
    readonly_fields = ['checklist_item', 'is_checked', 'notes']
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(LoanChecklistSubmission)
class LoanChecklistSubmissionAdmin(admin.ModelAdmin):
    list_display = [
        'submission_link',  # Make this the first column and clickable
        'loan_link',
        'submitted_by',
        'submitted_at',
        'checked_items_count',
        'notes_preview'
    ]
    list_filter = ['submitted_at', 'submitted_by']
    search_fields = ['loan__id', 'submitted_by__email', 'notes']
    readonly_fields = ['loan', 'submitted_by', 'submitted_at', 'checked_items_summary']

    inlines = [LoanChecklistItemCheckInline]

    fieldsets = (
        ('Submission Info', {
            'fields': ('loan', 'submitted_by', 'submitted_at', 'notes')
        }),
        ('Checklist Summary', {
            'fields': ('checked_items_summary',),
        }),
    )

    def submission_link(self, obj):
        """Make the submission itself clickable"""
        url = reverse('admin:finance_checklist_loanchecklistsubmission_change', args=[obj.pk])
        return format_html('<a href="{}" style="font-weight: bold; color: #0066cc;">Submission #{}</a>', url, obj.pk)

    submission_link.short_description = 'Submission'

    def loan_link(self, obj):
        url = reverse('admin:core_loan_change', args=[obj.loan.id])  # Replace 'core' with your actual app name
        return format_html('<a href="{}">Loan {}</a>', url, obj.loan.id)

    loan_link.short_description = 'Loan'

    def checked_items_count(self, obj):
        total_items = FinanceChecklistItem.objects.filter(is_active=True).count()
        checked_count = obj.item_checks.filter(is_checked=True).count()
        percentage = (checked_count / total_items * 100) if total_items > 0 else 0

        # Color coding
        if percentage == 100:
            color = "#28a745"  # Green
        elif percentage >= 50:
            color = "#ffc107"  # Yellow
        else:
            color = "#dc3545"  # Red

        return format_html(
            '<span style="color: {}; font-weight: bold;">{}/{} ({}%)</span>',
            color, checked_count, total_items, int(percentage)
        )

    checked_items_count.short_description = 'Progress'

    def notes_preview(self, obj):
        if obj.notes:
            return obj.notes[:50] + "..." if len(obj.notes) > 50 else obj.notes
        return "-"

    notes_preview.short_description = 'Notes'

    def checked_items_summary(self, obj):
        """Display summary of checked items"""
        checks = obj.item_checks.all().select_related('checklist_item')

        html = "<div style='max-height: 300px; overflow-y: auto; border: 1px solid #ddd; border-radius: 4px;'>"
        html += "<table style='width: 100%; border-collapse: collapse; margin: 0;'>"
        html += "<thead>"
        html += "<tr style='background: #f8f9fa; font-weight: bold; position: sticky; top: 0;'>"
        html += "<th style='padding: 10px; border-bottom: 2px solid #ddd; text-align: left;'>Item</th>"
        html += "<th style='padding: 10px; border-bottom: 2px solid #ddd; text-align: center; width: 100px;'>Status</th>"
        html += "<th style='padding: 10px; border-bottom: 2px solid #ddd; text-align: left;'>Notes</th>"
        html += "</tr>"
        html += "</thead>"
        html += "<tbody>"

        for check in checks:
            status_color = "#28a745" if check.is_checked else "#dc3545"
            status_icon = "✓" if check.is_checked else "✗"
            status_text = "Checked" if check.is_checked else "Not Checked"
            row_bg = "#f9f9f9" if check.is_checked else "#fff5f5"

            html += f"<tr style='background: {row_bg};'>"
            html += f"<td style='padding: 10px; border-bottom: 1px solid #eee; vertical-align: top;'>"
            html += f"<strong>{check.checklist_item.title}</strong>"
            if check.checklist_item.description:
                html += f"<br><small style='color: #666;'>{check.checklist_item.description}</small>"
            html += f"</td>"
            html += f"<td style='padding: 10px; border-bottom: 1px solid #eee; text-align: center; vertical-align: top;'>"
            html += f"<span style='color: {status_color}; font-weight: bold; font-size: 16px;'>{status_icon}</span><br>"
            html += f"<small style='color: {status_color}; font-weight: bold;'>{status_text}</small>"
            html += f"</td>"
            html += f"<td style='padding: 10px; border-bottom: 1px solid #eee; vertical-align: top;'>"
            html += f"<span style='color: #333;'>{check.notes or '-'}</span>"
            html += f"</td>"
            html += f"</tr>"

        html += "</tbody>"
        html += "</table></div>"

        # Add summary at the bottom
        total_items = checks.count()
        checked_count = checks.filter(is_checked=True).count()
        percentage = (checked_count / total_items * 100) if total_items > 0 else 0

        html += f"<div style='margin-top: 10px; padding: 10px; background: #f8f9fa; border-radius: 4px;'>"
        html += f"<strong>Summary:</strong> {checked_count}/{total_items} items completed ({int(percentage)}%)"
        html += f"</div>"

        return mark_safe(html)

    checked_items_summary.short_description = 'Checklist Items Summary'


@admin.register(LoanBook)
class LoanBookAdmin(admin.ModelAdmin):
    readonly_fields = ('loan',)
    list_display = (
        'loan', 'initial_amount', 'estate_net_value',
        'initial_fee_percentage', 'daily_fee_after_year_percentage', 'exit_fee_percentage',
        'created_at'
    )
    search_fields = ('loan__id',)  # Search by the related Loan's ID


@admin.register(EmailCommunication)
class EmailCommunicationAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'application_link', 'recipient_email', 'subject_truncated',
        'status', 'document_count', 'sent_by', 'created_at', 'sent_at'
    ]
    list_filter = ['status', 'created_at', 'sent_at', 'email_template']
    search_fields = ['recipient_email', 'subject', 'application__id']
    readonly_fields = ['created_at', 'sent_at', 'delivered_at', 'email_service_id']

    fieldsets = (
        ('Email Details', {
            'fields': ('application', 'recipient_email', 'recipient_name', 'subject', 'message')
        }),
        ('Settings', {
            'fields': ('email_template', 'status')
        }),
        ('Tracking', {
            'fields': ('sent_by', 'created_at', 'sent_at', 'delivered_at', 'email_service_id'),
            'classes': ('collapse',)
        }),
    )

    def application_link(self, obj):
        if obj.application:
            try:
                # Try different possible admin URL patterns for Application
                url = reverse('admin:core_application_change', args=[obj.application.id])
                return format_html('<a href="{}">{}</a>', url, obj.application.id)
            except:
                try:
                    # Alternative pattern
                    url = reverse('admin:applications_application_change', args=[obj.application.id])
                    return format_html('<a href="{}">{}</a>', url, obj.application.id)
                except:
                    # If reverse fails, just return the ID without link
                    return str(obj.application.id)
        return '-'

    application_link.short_description = 'Application'

    def subject_truncated(self, obj):
        return obj.subject[:50] + '...' if len(obj.subject) > 50 else obj.subject

    subject_truncated.short_description = 'Subject'

    def document_count(self, obj):
        count = obj.email_documents.count()
        return format_html('<span class="badge">{}</span>', count)

    document_count.short_description = 'Documents'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'application', 'sent_by'
        ).prefetch_related('email_documents')


@admin.register(EmailDocument)
class EmailDocumentAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'original_name', 'email_communication_link',
        'file_size_formatted', 'mime_type', 'created_at'
    ]
    list_filter = ['mime_type', 'created_at']
    search_fields = ['original_name', 'email_communication__subject']
    readonly_fields = ['file_size', 'created_at']

    def email_communication_link(self, obj):
        url = reverse('admin:document_emails_emailcommunication_change',
                      args=[obj.email_communication.id])
        return format_html('<a href="{}">{}</a>',
                           url, f"Email {obj.email_communication.id}")

    email_communication_link.short_description = 'Email Communication'

    def file_size_formatted(self, obj):
        size = obj.file_size
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        else:
            return f"{size / (1024 * 1024):.1f} MB"

    file_size_formatted.short_description = 'File Size'


@admin.register(EmailDeliveryLog)
class EmailDeliveryLogAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'email_communication_link', 'event_type',
        'timestamp', 'created_at'
    ]
    list_filter = ['event_type', 'timestamp', 'created_at']
    search_fields = ['email_communication__subject', 'email_communication__recipient_email']
    readonly_fields = ['timestamp', 'created_at', 'service_data']

    def email_communication_link(self, obj):
        url = reverse('admin:document_emails_emailcommunication_change',
                      args=[obj.email_communication.id])
        return format_html('<a href="{}">{}</a>',
                           url, f"Email {obj.email_communication.id}")

    email_communication_link.short_description = 'Email Communication'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('email_communication')
