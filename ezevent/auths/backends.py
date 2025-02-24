from django.contrib.auth.backends import BaseBackend
from rest_framework.permissions import IsAuthenticated, BasePermission
from .models import Users, UserRole
from .hashing import Harsher

class CustomAuthBackend(BaseBackend):
    def authenticate(self, request, email=None, password=None):
        try:
            user = Users.objects.get(email=email)
            if user and Harsher.verify_password(password, user.password):
                return user
        except Users.DoesNotExist:
            return None

class IsAdminUser(BasePermission):
    """
    Allowing access only to admin users.
    """
    def has_permission(self, request, view):
        user_role = UserRole.objects.filter(user=request.user).first()
        return user_role and user_role.role.name == 'admin'