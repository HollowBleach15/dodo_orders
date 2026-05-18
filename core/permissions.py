from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsAdminStaff(BasePermission):
    def has_permission(self, request, view):
        return _in_group(request.user, "admin_staff") or request.user.is_superuser


class IsOpsManager(BasePermission):
    def has_permission(self, request, view):
        return _in_group(request.user, "ops_manager") or request.user.is_staff


class IsBranchEmployee(BasePermission):
    def has_permission(self, request, view):
        return _in_group(request.user, "branch_employee")


class IsFranchiseOwner(BasePermission):
    def has_permission(self, request, view):
        return _in_group(request.user, "franchise_owner")


class IsManagerOrAbove(BasePermission):
    """ops_manager, admin_staff и is_staff — запись; остальные — только чтение."""
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return request.user and request.user.is_authenticated
        return (
            request.user.is_staff
            or _in_group(request.user, "admin_staff")
            or _in_group(request.user, "ops_manager")
        )


def _in_group(user, group_name: str) -> bool:
    return bool(
        user
        and user.is_authenticated
        and user.groups.filter(name=group_name).exists()
    )