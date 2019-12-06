from datetime import datetime, timedelta
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.signals import post_save
from django.urls import reverse
from django.utils.timezone import now
from RoasManager.settings import APPLICATION_URL, DEFAULT_FROM_EMAIL
from googleads import adwords
from django.core.mail import send_mail


BUDGET_ALERT_DAYS_COUNT = (
    (0, "Wyłącz"),
    (1, "1 dzień"),
    (2, "2 dni"),
    (3, "3 dni"),
    (4, "4 dni"),
    (5, "5 dni"),
)


class CustomUser(AbstractUser):

    def create_alert(self, message):
        from roas_manager.models import Alert
        print(message)
        alert = Alert.objects.create(date=now().date(), message=message)
        alert.user.set([self])
        alert.save()

    def check_cost_threshold(self, campaign_group, budget, yesterday_log):
        from roas_manager.tools import calculate_target_cost
        target_cost = round(calculate_target_cost(campaign_group), 2)
        if target_cost == 0 and self.alertsettings.budget_depleted is True:
            from roas_manager.tools import get_total_cost
            total_cost = get_total_cost(campaign_group)
            message = f'Konto: {campaign_group.account.account_name} | Grupa kampanii: {campaign_group.name} | ' \
                      f'Budżet {budget.to_spend} zł na okres {budget.date_from} - {budget.date_to} został ' \
                      f'przekroczony o {(budget.to_spend - total_cost) * -1}. Łączny koszt: {total_cost} zł. ' \
                      f'Wczorajszy koszt: {yesterday_log.cost} zł'
            self.create_alert(message)
            return (budget.to_spend - total_cost) * -1
        elif target_cost == 0 and self.alertsettings.budget_depleted is False:
            return None
        else:
            percent_difference = round((yesterday_log.cost/target_cost), 2)
            if percent_difference >= self.alertsettings.cost_threshold_upper:
                message = f'Konto: {campaign_group.account.account_name} | Grupa kampanii: {campaign_group.name} | ' \
                          f'Wczorajsze wydatki tej grupy kampanii przekroczyły próg ostrzeżenia. ' \
                          f'Koszt {yesterday_log.cost} zł to {percent_difference * 100}% kosztu docelowego' \
                          f' ({target_cost} zł). '
                self.create_alert(message)
                return percent_difference

            if percent_difference <= self.alertsettings.cost_threshold_lower:
                message = f'Konto: {campaign_group.account.account_name} | Grupa kampanii: {campaign_group.name} | ' \
                          f'Wczorajsze wydatki tej grupy kampanii były poniżej minimum prógu ostrzeżenia.' \
                          f'Koszt: {yesterday_log.cost} zł. Koszt docelowy: {target_cost} zł. ' \
                          f'Wczorajszy koszt to {percent_difference * 100}% kosztu docelowego'
                self.create_alert(message)
                return percent_difference
            else:
                return percent_difference

    def check_future_budget(self, campaign_group, budget):
        yesterday = (datetime.today() - timedelta(days=1)).date()
        budget_days_left = (budget.date_to - yesterday).days
        if budget_days_left <= self.alertsettings.no_new_budget:
            next_budget_first_day = (budget.date_to + timedelta(days=1))
            future_budget = self.budget_set.filter(campaign_group=campaign_group, date_from=next_budget_first_day)
            if future_budget.count() < 1:
                from roas_manager.models import Alert
                message = f'Konto: {campaign_group.account.account_name} | Grupa kampanii: {campaign_group.name} | ' \
                          f'Za {budget_days_left} dni kończy się okres obecnego budżetu ({budget.date_from} - ' \
                          f'{budget.date_to}), a nie został jeszcze dodany budżet obejmujący kolejne dni. Dodaj go, ' \
                          f'jeśli chcesz utrzymać regulację wydatków. Możesz to zrobić tutaj: ' \
                          f'{APPLICATION_URL}{reverse("add_budget", args=[campaign_group.id])}'
                self.create_alert(message)

    def check_alerts(self):
        self.find_campaigns_outside_groups()
        campaign_groups = self.campaigngroup_set.all()
        for campaign_group in campaign_groups:
            yesterday = (datetime.today() - timedelta(days=1)).date()
            budget = campaign_group.budget_set.filter(date_from__lte=yesterday, date_to__gte=yesterday)
            if not budget.exists():
                continue
            budget = budget.first()
            logs = campaign_group.log_set.filter(date__gte=budget.date_from, date__lte=budget.date_to)
            budget_days = (yesterday - budget.date_from).days + 1
            if logs.count() < budget_days:  # jeśli logów jest mniej niż dni od startu okresu, to znaczy że brakuje danych
                continue
            yesterday_log = campaign_group.log_set.filter(date=yesterday).first()
            self.check_cost_threshold(campaign_group, budget, yesterday_log)
            self.check_future_budget(campaign_group, budget)

    def find_campaigns_outside_groups(self):
        if self.alertsettings.campaign_group_coverage is False:
            return None
        accounts = self.account_set.all()
        for account in accounts:
            campaign_groups = account.campaigngroup_set.all()
            if campaign_groups.count() < 1:
                continue
            cg_ids = [campaign_group.campaign_group_id for campaign_group in campaign_groups]
            account_id = account.account_number
            adwords_client = adwords.AdWordsClient.LoadFromStorage()
            adwords_client.SetClientCustomerId(account_id)
            campaigns_service = adwords_client.GetService('CampaignService', version='v201809')
            selector = {
                'fields': ['Id', 'Name', 'Status', 'CampaignGroupId'],
                'predicates': [{
                    'field': 'Status',
                    'operator': 'EQUALS',
                    'values': 'ENABLED'
                }, {
                    'field': 'ServingStatus',
                    'operator': 'EQUALS',
                    'values': 'SERVING'
                }, {
                    'field': 'AdvertisingChannelSubType',
                    'operator': 'NOT_EQUALS',
                    'values': 'UNIVERSAL_APP_CAMPAIGN'
                }, {
                    'field': 'CampaignGroupId',
                    'operator': 'NOT_IN',
                    'values': cg_ids
                }]
            }
            campaigns = []
            page = campaigns_service.get(selector)

            if 'entries' in page:
                for campaign in page['entries']:
                    campaigns.append(campaign['name'])
            if len(campaigns) > 0:
                message = f"Na koncie {account.account_name} odnaleziono kampanie nie należące do żadnej z " \
                          f"grup kampanii dodanych do ROAS Managera. Ilość: {len(campaigns)}, nazwy: {campaigns}. " \
                          f"Dodaj je do właściwej grupy kampanii lub dodaj brakujące grupy kampanii do ROAS Managera."
                self.create_alert(message)

    def check_roi(self, campaign_group, yesterday_log):
        if yesterday_log.income and yesterday_log.cost and self.alertsettings.roi_threshold is not None:
            from roas_manager.models import GlobalSettings
            settings = GlobalSettings.get_settings()
            income = yesterday_log.income * settings.return_rate * settings.tax
            roi = round((income - yesterday_log.cost) / yesterday_log.cost, 2)
            if roi < self.alertsettings.roi_threshold:
                message = f"Konto: {campaign_group.account.account_name} | Grupa kampanii: {campaign_group.name} | " \
                          f"Wczorajsze ROI ({roi}) było mniejsze niż ustawione minimum " \
                          f"({self.alertsettings.roi_threshold}). "
                self.create_alert(message)
                subject = f'ROAS Manager | ROI poniżej ustawionego minimum'
                send_mail(subject, message, DEFAULT_FROM_EMAIL, [self.email])


class AlertSettings(models.Model):
    cost_threshold_upper = models.DecimalField(null=True, decimal_places=2, max_digits=4, default=1.8,
                                               verbose_name='Zbyt duże wydatki')
    cost_threshold_lower = models.DecimalField(null=True, decimal_places=2, max_digits=4, default=0.4,
                                               verbose_name='Zbyt małe wydatki')
    roi_threshold = models.DecimalField(null=True, decimal_places=2, max_digits=4, default=0,
                                        verbose_name='Minimalne ROI')
    campaign_group_coverage = models.BooleanField(default=True, verbose_name='Kampanie nie przypisane do grupy')
    budget_depleted = models.BooleanField(default=True, verbose_name='Przekroczenie budżetu')
    no_new_budget = models.IntegerField(choices=BUDGET_ALERT_DAYS_COUNT, default=3,
                                        verbose_name='Brak budżetu na kolejny okres')
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE)

    def __str__(self):
        return f'{self.user.username}'


def after_user_created(instance, created, **kwargs):
    if created:
        AlertSettings.objects.create(user=instance)


post_save.connect(after_user_created, sender=CustomUser)
