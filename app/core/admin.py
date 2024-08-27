"""
Django admin customization.
"""

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django import forms
from django.utils import timezone

from rangefilter.filters import DateRangeFilter

from django.utils.translation import gettext_lazy as _

from core import models
from core.models import LoanExtension, Transaction, Document

from rest_framework.authtoken.models import Token


class UserAdmin(BaseUserAdmin):
    """Define admin pages for users"""

    ordering = ["id"]
    list_display = ["email", "name"]
    actions = ['delete_selected_with_tokens']

    def delete_selected_with_tokens(self, request, queryset):
        for obj in queryset:
            # Delete related tokens of the user
            Token.objects.filter(user=obj).delete()  # delete relevant tokens here
            obj.delete()

    delete_selected_with_tokens.short_description = 'Delete selected users with related tokens'

    fieldsets = (
        (None, {"fields": ("email", "password", "team", "phone_number", "name", "address")}),
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
                "team",
                "is_active",
                "is_staff",
                "is_superuser",
                "phone_number",
                "address"
            )
        }),
    )


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
        (None, {"fields": ("amount", "term", "user", "deceased", "dispute", "assigned_to", "last_updated_by",)}),
        (_("Details"), {"fields": (
            "approved", "is_rejected", "rejected_reason", "rejected_date", "undertaking_ready", "loan_agreement_ready",
            "value_of_the_estate_after_expenses")}),
    )

    readonly_fields = (
        'id', 'last_updated_by', 'deceased_full_name', 'dispute_details', 'date_submitted', 'deceased', 'dispute',
        'user', "rejected_date", "undertaking_ready", "loan_agreement_ready", "value_of_the_estate_after_expenses")

    search_fields = ["id", ]
    list_display = ("id", "user", "assigned_to", "deceased_full_name", "dispute_details",
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
                "approved_by", "last_updated_by",)
        }),
        (_("Settled Info"), {
            "fields": (
                "is_settled", "settled_date"),

        }),
        (_("Read-only Info"), {
            "fields": ("maturity_date", "current_balance", "amount_paid", "extension_fees_total",),

        }),
    )

    readonly_fields = (
        'application', "maturity_date", "current_balance", "amount_paid", "last_updated_by", "approved_by",
        "extension_fees_total")
    ordering = ["id"]
    inlines = [TransactionInline, LoanExtensionInline]
    list_display = ["id", "application", "amount_agreed", "term_agreed", "approved_by", "last_updated_by"]

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
