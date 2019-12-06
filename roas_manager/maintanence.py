from django.core.exceptions import ObjectDoesNotExist
from django.core.mail import send_mail
from roas_manager.google_ads import save_report_results
from roas_manager.models import Account, Log, Strategy
from roas_manager.tools import event_alert
from roas_manager.google_ads import campaign_group_report, update_roas
from RoasManager.settings import DEFAULT_FROM_EMAIL
from users.models import CustomUser
from datetime import datetime, timedelta
from googleads.errors import GoogleAdsServerFault
import logging


logger = logging.getLogger(__name__)


def date_range(start_date, end_date):
    dates_list = [start_date]
    delta = timedelta(days=1)
    while start_date < end_date:
        start_date += delta
        dates_list.append(start_date)
    return dates_list


def get_continuous_dates(dates_list):  # z listy dat wyciąga pierwszy napotkany ciąg artymetyczny +1
    continuous_dates = []
    yesterday = (datetime.today() - timedelta(days=1)).date()
    day = datetime.today().date() - yesterday
    for num in range(len(dates_list) - 1):
        if (dates_list[num + 1] - dates_list[num]) == day:
            continuous_dates.append(dates_list[num])
        else:
            if continuous_dates:
                if dates_list[num] - continuous_dates[-1] == day:
                    continuous_dates.append(dates_list[num])
                break
    if continuous_dates:
        if dates_list[-1] - continuous_dates[-1] == day:
            continuous_dates.append(dates_list[-1])
    return continuous_dates


def lists_difference(li1, li2):
    return list(set(li1) - set(li2))


def log_continuity_check(adwords_client, accounts=None):
    yesterday = (datetime.today() - timedelta(days=1)).date()
    if accounts is None:
        accounts = Account.objects.all()
    for account in accounts:
        campaign_groups = account.campaigngroup_set.all()
        if campaign_groups.exists():
            try:
                adwords_client.SetClientCustomerId(account.account_number)
            except GoogleAdsServerFault:
                logger.error(f'{account.account_name} | Sprawdzanie logów | Błąd podczas próby dostępu do konta '
                             f'przez API')
                continue
            for campaign_group in campaign_groups:
                missing_days_list = []
                try:
                    budget = campaign_group.budget_set.filter(date_from__lte=yesterday, date_to__gte=yesterday).get()
                    days_list = date_range(budget.date_from, yesterday)
                    for day in days_list:
                        log, created = Log.objects.update_or_create(campaign_group=campaign_group, date=day)
                        if (log.cost or log.clicks) is None:
                            missing_days_list.append(day)
                            print(f"{campaign_group.name} | Brakuje danych o koszcie/klikach"
                                  f" na dzień: {log.date.strftime('%Y%m%d')}")
                    if missing_days_list:
                        continuous_days_list = get_continuous_dates(missing_days_list)
                        remaining_days = lists_difference(missing_days_list, continuous_days_list)
                        if continuous_days_list:  # dla dni następujących po sobie, uzupełnianie uruchamia się zbiorczo
                            print(f"{campaign_group.name} | Brakuje logów za dni "
                                  f"{continuous_days_list[0].strftime('%Y%m%d')}"
                                  f" - {continuous_days_list[-1].strftime('%Y%m%d')}")
                            report = campaign_group_report(adwords_client,
                                                           [campaign_group],
                                                           continuous_days_list[0].strftime("%Y%m%d"),
                                                           continuous_days_list[-1].strftime("%Y%m%d"))
                            save_report_results(report)
                            print(f"{campaign_group.name} | Logi uzupełnione.")
                        if remaining_days:  # dla pozostałych, pojedynczych dni, uzupełnianie uruchamia się w pętli
                            str_dates = [i.strftime("%Y%m%d") for i in remaining_days]
                            print(f"{campaign_group.name} | Brakuje logów za dni {str_dates}")
                            for day in remaining_days:
                                report = campaign_group_report(adwords_client,
                                                               [campaign_group],
                                                               day.strftime("%Y%m%d"),
                                                               day.strftime("%Y%m%d"))
                                save_report_results(report)
                            print(f"{campaign_group.name} | Logi uzupełnione.")

                except ObjectDoesNotExist:
                    message = f"Grupa kampanii: {campaign_group.name} nie ma przypisanego budżetu na dzień bieżący."
                    event_alert(message, campaign_group=campaign_group)
        else:
            message = f'{datetime.now()} | Konto {account.account_name} nie ma przypisanych żadnych grup kampanii!'
            print(message)
    print(f"{datetime.now()} | Zakończone sprawdzanie ciągłości logów\n")


def global_roas_update(adwords_client, accounts):
    for account in accounts:
        campaign_groups = account.campaigngroup_set.all()
        if campaign_groups.exists():
            try:
                adwords_client.SetClientCustomerId(account.account_number)
            except GoogleAdsServerFault:
                logging.error(f'{account.account_name} | Błąd podczas próby dostępu do konta przez API')
                continue
            yesterday = ((datetime.today() - timedelta(days=1)).date())
            yesterday_string = yesterday.strftime("%Y%m%d")
            strategies = []
            for cg in campaign_groups:
                try:  # sprawdź czy dla każdej grupy kampanii jest log za wczoraj
                    log = cg.log_set.filter(date=yesterday).get()
                    if log.cost is None:  # sprawdź, czy we wczorajszym logu jest koszt
                        print(f"Grupa kampanii: {cg.name} | Wczorajszy log nie zawiera danych o koszcie, aktualizuję.")
                        report = campaign_group_report(adwords_client, [cg], yesterday_string, yesterday_string)
                        # report = {15675687: [['2019-09-23', 0.0, 0.0]]}
                        save_report_results(report)
                        print(f"Grupa kampanii: {cg.name} | Koszt we wczorajszym logu został zaktualizowany.")
                        # sprawdzenie wartości log.cost - czy przy drugim princie Python ją podmieni? użyć continue
                except ObjectDoesNotExist:  # jeżeli nie ma loga za wczoraj, pobierz raport i utwórz go
                    print(f"Grupa kampanii: {cg.name} | Nie odnaleziono loga za wczoraj, próba aktualizacji.")
                    report = campaign_group_report(adwords_client, [cg], yesterday_string, yesterday_string)
                    save_report_results(report)
                    try:  # sprawdź, czy log jest rzeczywiście utworzony
                        cg.log_set.filter(date=yesterday).get()
                        print(f"Grupa kampanii: {cg.name} | Koszt we wczorajszym logu został zaktualizowany.")
                    except ObjectDoesNotExist:
                        logger.warning(f"Grupa kampanii: {cg.name} | Nie odnaleziono loga mimo wcześniejszej próby"
                                       f" jego utworzenia. Aktualizacja ROAS pominięta!")
                        continue
                [strategies.append(strategy) for strategy in Strategy.objects.filter(campaign_group=cg)]
            update_roas(strategies, account, adwords_client, override_check=True, dry_run=False)
        else:
            print(f'Konto {account.account_name} nie ma przypisanych żadnych grup kampanii.')


def check_for_alerts():
    for user in CustomUser.objects.all():
        user.check_alerts()


def send_alerts():
    for user in CustomUser.objects.all():
        message = ''
        alerts = user.alert_set.filter(date=datetime.now().date())
        if alerts.exists():
            for alert in alerts:
                message += '- ' + alert.message + '\n'
            subject = f'ROAS Manager - alerty na dzień {datetime.now().date()}'
            send_mail(subject, message, DEFAULT_FROM_EMAIL, [user.email])
