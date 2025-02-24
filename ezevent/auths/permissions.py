from rest_framework.permissions import BasePermission

class IsAdminOrHasRole(BasePermission):
    def has_permission(self, request, view):
        # Check if user is a superuser
        if request.user and request.user.is_superuser:
            return True

        # Get user role from request attribute
        user_role = getattr(request, 'user_role', None)
        allowed_roles = getattr(view, 'allowed_roles', [])

        print(f"User role: {user_role}, Allowed roles: {allowed_roles}")

        return user_role in allowed_roles



