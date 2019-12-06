from django.core.management.base import BaseCommand
from roas_manager.google_sheets import update_google_sheets
from roas_manager.models import Account


class Command(BaseCommand):
    help = 'Komenda aktualizująca ROAS dla wszystkich strategii w bazie danych'

    def handle(self, *args, **kwargs):
        accounts = Account.objects.all()
        update_google_sheets(accounts)

