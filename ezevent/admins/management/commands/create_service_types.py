# from django.core.management.base import BaseCommand
# from nfixbackend.models import ServiceType

# class Command(BaseCommand):
#     help = 'Create initial services for the application'

#     def handle(self, *args, **kwargs):
#         services = ['baby_sitter', 'real_estate_broker', 'plumber']
#         for service_name in services:
#             service, created = ServiceType.objects.get_or_create(name=service_name)
#             if created:
#                 self.stdout.write(self.style.SUCCESS(f'service "{service_name}" created.'))
#             else:
#                 self.stdout.write(self.style.WARNING(f'service "{service_name}" already exists.'))