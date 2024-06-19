"""
Django admin customization.
"""

from django.contrib import admin
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


admin.site.register(models.User, UserAdmin)
admin.site.register(models.Team)
admin.site.register(models.Address)
