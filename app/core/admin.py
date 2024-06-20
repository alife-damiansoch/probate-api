"""
Django admin customization.
"""

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django import forms
from django.utils.html import format_html_join

from django.utils.translation import gettext_lazy as _

from core import models


class UserAdmin(BaseUserAdmin):
    """Define admin pages for users"""

    ordering = ["id"]
    list_display = ["email", "name"]

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


class ApplicantInline(admin.StackedInline):
    model = models.Applicant
    extra = 0


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


class ApplicationAdmin(admin.ModelAdmin):
    ordering = ["id"]
    form = ApplicationForm
    inlines = [ApplicantInline, EstateInline]
    readonly_fields = ('id', 'last_updated_by',)
    list_display = ('id', 'user', 'assigned_to', 'deceased_full_name', 'dispute_details')
    search_fields = ['id', ]

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


admin.site.register(models.User, UserAdmin)
admin.site.register(models.Team)
admin.site.register(models.Address)
admin.site.register(models.Application, ApplicationAdmin)
admin.site.register(models.Deceased)
admin.site.register(models.Estate)
admin.site.register(models.Dispute)
