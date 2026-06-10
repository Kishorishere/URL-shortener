from rest_framework.permissions import BasePermission


class IsVerifiedUser(BasePermission):
    message = "Email verification required."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_verified
        )
