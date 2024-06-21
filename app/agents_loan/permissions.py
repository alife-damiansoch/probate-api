from rest_framework import permissions


class IsStaff(permissions.BasePermission):
    """
    Custom permission to only allow staff users to view the list
    """

    def has_permission(self, request, view):
        return request.user.is_staff
