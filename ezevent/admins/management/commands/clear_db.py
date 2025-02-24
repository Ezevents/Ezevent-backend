from django.core.management.base import BaseCommand
from django.apps import apps

class Command(BaseCommand):
    help = 'Clears all data from the database'

    def handle(self, *args, **kwargs):
        models = apps.get_models()
        for model in models:
            model.objects.all().delete()
        self.stdout.write(self.style.SUCCESS('Database cleared.'))