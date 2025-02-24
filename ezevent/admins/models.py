from django.db import models
from django.utils import timezone
from auths.models import Role

class SignupToken(models.Model):
    token = models.CharField(max_length=6, unique=True, null=True, blank=True, default=None)
    role = models.ForeignKey(Role, on_delete=models.CASCADE, null=True, blank=True, default= None)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    used = models.BooleanField(default=False)

    def is_valid(self):
        return timezone.now() < self.expires_at and not self.used