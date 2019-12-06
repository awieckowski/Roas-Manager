from django.core.management.base import BaseCommand
from roas_manager.google_cloud_platform import *
from roas_manager.models import Account
from users.models import CustomUser
from datetime import datetime, timedelta


class Command(BaseCommand):
    help = 'Komenda pobierające dane z GCP'

    def handle(self, *args, **kwargs):
        accounts = Account.objects.all()
        yesterday = (datetime.today() - timedelta(days=1)).date()
        save_gcp_data(accounts, yesterday)

