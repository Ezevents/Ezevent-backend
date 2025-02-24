from django.core.management.base import BaseCommand
from auths.models import Role

class Command(BaseCommand):
    help = 'Create initial roles for the application'

    def handle(self, *args, **kwargs):
        roles = ['admin', 'promoter', 'client']
        for role_name in roles:
            role, created = Role.objects.get_or_create(name=role_name)
            if created:
                self.stdout.write(self.style.SUCCESS(f'Role "{role_name}" created.'))
            else:
                self.stdout.write(self.style.WARNING(f'Role "{role_name}" already exists.'))