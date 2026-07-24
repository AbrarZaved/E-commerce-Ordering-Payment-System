from rest_framework import permissions


class IsAdminOrReadOnly(permissions.BasePermission):
    """Allow read-only access to anyone, writes only to staff/admin users."""

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_staff)


class IsOwner(permissions.BasePermission):
    """Object-level permission: only the owner of an object may access it.

    Assumes the model instance exposes a ``user`` attribute.
    """

    def has_object_permission(self, request, view, obj):
        owner = getattr(obj, "user", None)
        return owner == request.user
