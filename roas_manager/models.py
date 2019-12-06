from django.db import models
from django.utils.timezone import now
from users.models import CustomUser
import decimal

VERIFICATION_STATES = (
    (1, "Niezweryfikowany"),
    (2, "Zatwierdzony"),
    (3, "Do poprawy")
)


class Account(models.Model):
    account_number = models.CharField(verbose_name='Numer konta', max_length=128)
    account_name = models.CharField(verbose_name='Nazwa konta', max_length=128)
    user = models.ManyToManyField(CustomUser, verbose_name='Opiekun konta')

    class Meta:
        ordering = ['account_name']

    def __str__(self):
        return f'{self.account_name}'


class CampaignGroup(models.Model):
    name = models.CharField(verbose_name='Nazwa', max_length=128)
    account = models.ForeignKey(Account, on_delete=models.CASCADE, null=True, verbose_name='Konto Google Ads')
    campaign_group_id = models.CharField(max_length=32, null=True, verbose_name='Id grupy w Google Ads')
    sheet_id = models.CharField(max_length=32, null=True, blank=True, verbose_name='Id arkusza Google Sheets')
    sql_query = models.TextField(null=True, blank=True, verbose_name='Kwerenda SQL BigQuery')
    user = models.ManyToManyField(CustomUser, verbose_name='Opiekun')

    class Meta:
        ordering = ['account']

    def __str__(self):
        return f'{self.name} - {self.account.account_name}'


class Log(models.Model):
    campaign_group = models.ForeignKey(CampaignGroup, on_delete=models.CASCADE, null=True)
    date = models.DateField(default=now)
    cost = models.DecimalField(null=True, decimal_places=2, max_digits=15)
    clicks = models.IntegerField(null=True)
    roas_before = models.DecimalField(null=True, decimal_places=2, max_digits=10)
    roas_after = models.DecimalField(null=True, decimal_places=2, max_digits=10)
    gmv = models.DecimalField(null=True, decimal_places=2, max_digits=15)
    income = models.DecimalField(null=True, decimal_places=2, max_digits=15)
    transactions = models.IntegerField(null=True)

    class Meta:
        ordering = ['date']

    def __str__(self):
        return f'{self.campaign_group.account.account_name} | {self.campaign_group.name} | {self.date}'


class Budget(models.Model):
    to_spend = models.DecimalField(decimal_places=2, max_digits=15, verbose_name='Kwota do wydania')
    date_from = models.DateField(default=now, verbose_name='Data rozpoczęcia')
    date_to = models.DateField(default=now, verbose_name='Data zakończenia')
    campaign_group = models.ForeignKey(CampaignGroup, on_delete=models.CASCADE, null=True,
                                       verbose_name='Przypisana grupa kampanii')
    user = models.ManyToManyField(CustomUser, verbose_name="Właściciel")
    verifying_user = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True,
                                       verbose_name='Osoba weryfikująca', related_name='budget_to_verify')
    verified = models.IntegerField(choices=VERIFICATION_STATES, default=1)

    def __str__(self):
        return f'{self.campaign_group.name} | {self.date_from} - {self.date_to}'


class Strategy(models.Model):
    name = models.CharField(max_length=128)
    budget = models.ManyToManyField(Budget)
    make_changes = models.BooleanField(default=False)
    account = models.ForeignKey(Account, on_delete=models.CASCADE, null=True)
    campaign_group = models.ForeignKey(CampaignGroup, on_delete=models.CASCADE, null=True)
    strategy_id = models.CharField(max_length=32, null=True)
    user = models.ManyToManyField(CustomUser, verbose_name='Opiekun')

    class Meta:
        ordering = ['account', 'name']

    def __str__(self):
        return f'{self.name}'


class GlobalSettings(models.Model):
    class Meta:
        get_latest_by = 'id'
    tax = models.DecimalField(decimal_places=2, max_digits=6, default=decimal.Decimal('1.00'))
    return_rate = models.DecimalField(decimal_places=2, max_digits=6, default=decimal.Decimal('1.00'))

    @classmethod
    def get_settings(cls):
        try:
            return cls.objects.latest()
        except cls.DoesNotExist:
            return cls.objects.create()


class Campaign(models.Model):
    name = models.CharField(max_length=256, verbose_name='Nazwa')
    type = models.CharField(max_length=96, verbose_name='Typ kampanii', null=True)
    campaign_id = models.CharField(max_length=32, null=True, verbose_name='Id kampanii w Google Ads')
    account = models.ForeignKey(Account, on_delete=models.CASCADE, null=True, verbose_name='Konto Google Ads')
    strategy = models.ForeignKey(Strategy, on_delete=models.CASCADE, null=True, verbose_name='Strategia')
    roas_modifier = models.DecimalField(null=True, decimal_places=2, max_digits=4, verbose_name='Modyfikator ROAS')
    manage_roas = models.BooleanField(default=False, verbose_name='Regulacja')
    user = models.ManyToManyField(CustomUser, verbose_name='Opiekun')

    class Meta:
        ordering = ['account']

    def __str__(self):
        return f'{self.name}'


class CampaignRoasLog(models.Model):
    date = models.DateField(default=now)
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, null=True)
    account = models.ForeignKey(Account, on_delete=models.CASCADE, null=True)
    roas_before = models.DecimalField(null=True, decimal_places=2, max_digits=6)
    roas_after = models.DecimalField(null=True, decimal_places=2, max_digits=6)

    def __str__(self):
        return f'{self.campaign.account.account_name} | {self.campaign.name} | {self.date}'


class Alert(models.Model):
    date = models.DateField(default=now)
    message = models.TextField(max_length=256)
    user = models.ManyToManyField(CustomUser)

    class Meta:
        ordering = ['date']

    def __str__(self):
        return f'{self.date}'
