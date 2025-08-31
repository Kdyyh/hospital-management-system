"""
Custom permission classes for role and group based access control.
"""
from rest_framework.permissions import BasePermission, SAFE_METHODS

ADMIN_ROLES = {"admin", "core", "super"}

class IsAdminRole(BasePermission):
    """Allow access only to users with an administrative role."""
    def has_permission(self, request, view) -> bool:  # type: ignore[override]
        user = getattr(request, "user", None)
        return bool(user and user.is_authenticated and getattr(user, "role", None) in ADMIN_ROLES)

class IsPatientRole(BasePermission):
    """Allow access only to users with the patient role."""
    def has_permission(self, request, view) -> bool:  # type: ignore[override]
        user = getattr(request, "user", None)
        return bool(user and user.is_authenticated and getattr(user, "role", None) == "patient")

class IsSuper(BasePermission):
    """Only super admin."""
    def has_permission(self, request, view) -> bool:
        user = getattr(request, "user", None)
        return bool(user and user.is_authenticated and getattr(user, "role", None) == "super")

class IsCoreOrSuper(BasePermission):
    """core or super."""
    def has_permission(self, request, view) -> bool:
        user = getattr(request, "user", None)
        return bool(user and user.is_authenticated and getattr(user, "role", None) in {"core", "super"})

class ReadOnly(BasePermission):
    """Allow read‑only access (GET, HEAD, OPTIONS)."""
    def has_permission(self, request, view) -> bool:  # type: ignore[override]
        return request.method in SAFE_METHODS

class IsSameGroup(BasePermission):
    """User must be in the same group as the object (expects `obj.group_id`)."""
    def has_object_permission(self, request, view, obj) -> bool:
        user = getattr(request, "user", None)
        if not (user and user.is_authenticated):
            return False
        if getattr(user, "role", None) == "super":
            return True
        return getattr(user, "group_id", None) and getattr(obj, "group_id", None) == user.group_id
