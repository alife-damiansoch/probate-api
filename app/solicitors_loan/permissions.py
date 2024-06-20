from rest_framework import permissions


class IsNonStaff(permissions.BasePermission):
    """
    Custom permission to only allow staff users to view the list
    """

    def has_permission(self, request, view):
        return not request.user.is_staff
