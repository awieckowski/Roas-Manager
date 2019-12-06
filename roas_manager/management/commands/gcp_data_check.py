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
        for user in CustomUser.objects.all():
            campaign_groups = user.campaigngroup_set.all()
            for campaign_group in campaign_groups:
                yesterday = (datetime.today() - timedelta(days=1)).date()
                budget = campaign_group.budget_set.filter(date_from__lte=yesterday, date_to__gte=yesterday)
                if not budget.exists():
                    continue
                yesterday_log = campaign_group.log_set.filter(date=yesterday)
                if not yesterday_log.exists():
                    continue
                yesterday_log = yesterday_log.first()
                if yesterday_log.cost is None or yesterday_log.income is None:
                    continue
                user.check_roi(campaign_group, yesterday_log)
