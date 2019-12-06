from django.core.management.base import BaseCommand
from roas_manager.maintanence import *


class Command(BaseCommand):
    help = 'Komenda aktualizująca ROAS dla wszystkich strategii w bazie danych'

    def handle(self, *args, **kwargs):
        check_for_alerts()
        send_alerts()
