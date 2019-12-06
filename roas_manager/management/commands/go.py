from django.core.management.base import BaseCommand
from roas_manager.models import Account
from roas_manager.maintanence import log_continuity_check, global_roas_update, check_for_alerts, send_alerts
from roas_manager.google_sheets import update_google_sheets
from roas_manager.google_ads import set_roas_at_campaigns_wrapper
from googleads import adwords
import logging


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Komenda aktualizująca ROAS dla wszystkich strategii w bazie danych'

    def handle(self, *args, **kwargs):
        logger.info("Start codziennej aktualizacji")
        accounts = Account.objects.all()
        adwords_client = adwords.AdWordsClient.LoadFromStorage()
        log_continuity_check(adwords_client, accounts)
        logger.info("Ukończone sprawdzanie ciągłości logów")
        global_roas_update(adwords_client, accounts)  # Ustaw tROAS
        logger.info("Ukończona aktualizacja ROAS w strategiach")
        set_roas_at_campaigns_wrapper(adwords_client, accounts=accounts)
        logger.info("Ukończona aktualizacja ROAS w kampaniach")
        update_google_sheets(accounts)  # Zaktualizuj arkusze
        logger.info("Ukończona aktualizacja arkuszy gsheets")
        check_for_alerts()
        send_alerts()
        logger.info("Alerty sprawdzone i wysłane - koniec codziennej aktualizacji")

