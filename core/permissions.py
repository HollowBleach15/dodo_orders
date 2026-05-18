from rest_framework.permissions import BasePermission, SAFE_METHODS
from django.contrib.auth.models import User


class IsAdminStaff(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        if not isinstance(user, User):
            return False
        return user.is_superuser or _in_group(user, "admin_staff")


class IsOpsManager(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        if not isinstance(user, User):
            return False
        return user.is_staff or _in_group(user, "ops_manager")


class IsBranchEmployee(BasePermission):
    def has_permission(self, request, view):
        def has_permission(self, request, view):
            user = request.user
            if not isinstance(user, User):
                return False
            return _in_group(user, "branch_employee")


class IsFranchiseOwner(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        if not isinstance(user, User):
            return False
        return _in_group(user, "franchise_owner")


class IsManagerOrAbove(BasePermission):
    """ops_manager, admin_staff и is_staff — запись; остальные — только чтение."""
    def has_permission(self, request, view):
        user = request.user
        if not isinstance(user, User):
            return False
        if request.method in SAFE_METHODS:
            return user.is_authenticated
        return (
            user.is_staff
            or _in_group(user, "admin_staff")
            or _in_group(user, "ops_manager")
        )


def _in_group(user: User, group_name: str) -> bool:
    return user.groups.filter(name=group_name).exists()