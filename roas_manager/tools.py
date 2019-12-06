from users.models import CustomUser
from roas_manager.models import Strategy, Log, GlobalSettings, Alert, CampaignGroup
from datetime import datetime, timedelta
from django.core.exceptions import ObjectDoesNotExist
from django.core.mail import send_mail
from django.urls import reverse
from django.db.models import Sum
from RoasManager.settings import DEFAULT_FROM_EMAIL, APPLICATION_URL
import random
import logging


logger = logging.getLogger(__name__)


def get_total_cost(campaign_group):
    yesterday = datetime.today() - timedelta(days=1)
    budget = campaign_group.budget_set.filter(date_from__lte=yesterday, date_to__gte=yesterday).get()
    total_cost = campaign_group.log_set.all().filter(date__gte=budget.date_from, date__lte=yesterday) \
        .order_by('date').aggregate(Sum('cost'))['cost__sum']
    return total_cost


def calculate_target_cost(campaign_group):
    yesterday = datetime.today() - timedelta(days=1)
    budget = campaign_group.budget_set.filter(date_from__lte=yesterday, date_to__gte=yesterday).get()
    yesterday = (datetime.today() - timedelta(days=1)).date()
    total_cost = get_total_cost(campaign_group)
    remaining_days = (budget.date_to - yesterday).days
    budget_remaining = budget.to_spend - total_cost
    if budget_remaining < 0 and not remaining_days == 0:
        target_cost = 0
    else:
        if remaining_days == 0:
            target_cost = campaign_group.log_set.get(date=yesterday).cost
        else:
            target_cost = budget_remaining / remaining_days
    return target_cost


def calculate_costs_difference(campaign_group, target_cost):
    if target_cost < 0:  # koszt docelowy spadnie poniżej zera w sytuacji przekroczenia budżetu
        target_cost = 0
    yesterday = datetime.today() - timedelta(days=1)
    log = Log.objects.get(date=yesterday, campaign_group=campaign_group)
    try:
        result = round((log.cost/target_cost), 2)
    except ZeroDivisionError:
        result = 2  # przekroczenie budżetu = koszt dzienny przekroczony o 200%
    return result


def msg(week_days, roas, diffr):
    if roas == 0:
        print('Koszt wyniósł %.0f%% kosztu docel.: reguła dla %s, ROAS bez zmian' % (diffr * 100, week_days))
    else:
        print('Koszt wyniósł %.0f%% kosztu docel.: reguła dla %s, ROAS do zmiany o %.0f%%' % (
            diffr * 100, week_days, roas * 100))


def get_roas_multiplier(difference):
    yesterday = datetime.today() - timedelta(days=1)
    week_day_yesterday = yesterday.weekday() + 1

    # niedziela, poniedziałek, wtorek
    if week_day_yesterday == 7 or week_day_yesterday == 1 or week_day_yesterday == 2:

        dni = 'nd-wt'
        # w nd-wt zwykle wydaje się za dużo, więc zwiększaj ROAS jeśli wydało się choćby odrobinę za mało.
        # gdy różnica procentowa jest mniejsza od jeden, wydało się za mało - zmniejsz ROAS
        if difference <= 0.8:
            x = -0.15
            msg(dni, x, difference)
            return x
        elif 0.9 >= difference > 0.8:
            x = -0.1
            msg(dni, x, difference)
            return x
        elif 0.95 >= difference > 0.9:
            x = -0.05
            msg(dni, x, difference)
            return x

        # w nd-wt zwykle wydaje się za dużo, więc zmniejszaj ROAS tylko, jeśli wydało się dużo za dużo.
        # gdy procent różnicy jest większa od jeden, wydało się za dużo - zwiększ ROAS
        elif difference >= 1.4:
            x = 0.15
            msg(dni, x, difference)
            return x
        elif 1.3 <= difference < 1.4:
            x = 0.1
            msg(dni, x, difference)
            return x
        elif 1.2 <= difference < 1.3:
            x = 0.05
            msg(dni, x, difference)
            return x
        else:
            x = 0
            msg(dni, x, difference)
            return x

    # środa, czwartek
    elif week_day_yesterday == 3 or week_day_yesterday == 4:

        dni = 'sr-czw'

        # gdy procent różnicy jest mniejszy od jeden, wydało się za mało - zmniejsz ROAS
        if difference <= 0.8:
            x = -0.15
            msg(dni, x, difference)
            return x
        elif 0.86 >= difference > 0.8:
            x = -0.1
            msg(dni, x, difference)
            return x
        elif 0.92 >= difference > 0.86:
            x = -0.05
            msg(dni, x, difference)
            return x

        # gdy procent różnicy jest większy od jeden, wydało się za dużo - zwiększ ROAS
        elif difference >= 1.2:
            x = 0.15
            msg(dni, x, difference)
            return x
        elif 1.14 <= difference < 1.2:
            x = 0.1
            msg(dni, x, difference)
            return x
        elif 1.08 <= difference < 1.14:
            x = 0.05
            msg(dni, x, difference)
            return x
        else:
            x = 0
            msg(dni, x, difference)
            return x

    # piątek, sobota
    else:
        dni = 'pt-sb'
        # W pt-sb zwykle wydaje się za mało, więc zmniejsz ROAS tylko jeśli wydało się dużo za mało
        # gdy procent różnicy jest mniejszy od jeden, wydało się za mało - zmniejsz ROAS
        if difference <= 0.6:
            x = -0.15
            msg(dni, x, difference)
            return x
        elif 0.7 >= difference > 0.6:
            x = -0.1
            msg(dni, x, difference)
            return x
        elif 0.8 >= difference > 0.7:
            x = -0.05
            msg(dni, x, difference)
            return x

        # W pt-sb zwykle wydaje się za mało, więc jeśli wydało się nawet odrobinę za dużo, zwiększaj ROAS.
        # gdy procent różnicy jest większy od jeden, zwiększ ROAS
        elif difference >= 1.2:
            x = 0.15
            msg(dni, x, difference)
            return x
        elif 1.13 <= difference < 1.2:
            x = 0.10
            msg(dni, x, difference)
            return x
        elif 1.05 <= difference < 1.13:
            x = -0.05
            msg(dni, x, difference)
            return x
        else:
            x = 0
            msg(dni, x, difference)
            return 0


def get_overview_table(date):
    date = (date - timedelta(days=1))
    settings = GlobalSettings.get_settings()
    campaign_groups = CampaignGroup.objects.all().prefetch_related('strategy_set')
    table = []
    for campaign_group in campaign_groups:
        try:
            budget = campaign_group.budget_set.filter(date_from__lte=date, date_to__gte=date).first()
        except:
            budget = None
        strategies = campaign_group.strategy_set.all().select_related('account')
        if not budget:  # jeśli nie ma budżetu na wybraną datę:
            for strategy in strategies:
                row = [strategy, strategy.account.account_name]
                row.extend([None for _ in range(10)])
                table.append(row)
            continue
        budget_days = (date - budget.date_from).days + 1
        logs = list(campaign_group.log_set.filter(date__gte=budget.date_from, date__lte=date).order_by('date'))
        if len(logs) < budget_days:  # sprawdzanie czy są logi za cały okres budżetu
            for strategy in strategies:
                row = [strategy, strategy.account.account_name]
                row.extend(['--' for _ in range(10)])
                table.append(row)
            continue
        logs_complete = True
        total_cost = 0
        for log in logs:  # sprawdzanie czy są dane kosztowe za cały okres budżetu
            total_cost += log.cost
            if log.cost is None:
                logs_complete = False
                break
        # total_cost = campaign_group.log_set.all().filter(date__gte=budget.date_from, date__lte=date) \
        #     .order_by('date').aggregate(Sum('cost'))['cost__sum']
        if logs_complete is False:
            total_cost = '--'
            remaining_funds = '--'
            target_cost = '--'
            percent_budget_spent = '--'
            percent_budget_target = '--'
        else:
            remaining_funds = budget.to_spend - total_cost
            if total_cost > budget.to_spend:
                target_cost = 0
            else:
                remaining_days = int((budget.date_to - date).days)
                if remaining_days == 0:
                    target_cost = remaining_funds
                else:
                    target_cost = round(remaining_funds / int((budget.date_to - date).days), 2)
            percent_budget_spent = round((total_cost / budget.to_spend), 4)
            percent_budget_target = round(((budget.to_spend / (budget.date_to.day + 1 - budget.date_from.day))
                                           / budget.to_spend) * (date.day + 1 - budget.date_from.day), 4)
        last_log = logs[-1]
        # last_log = logs.reverse()[0]
        roas_before = int(last_log.roas_before * 100) if last_log.roas_before else '--'
        roas_after = int(last_log.roas_after * 100) if last_log.roas_after else '--'
        gmv = last_log.gmv * settings.return_rate if last_log.gmv else '--'
        income = last_log.income * settings.return_rate * settings.tax if last_log.income else '--'
        if last_log.income is None or last_log.cost is None:
            roi = '--'
        else:
            roi = round(((income - last_log.cost) / last_log.cost), 2)
        for strategy in strategies:
            row = [strategy, strategy.account.account_name, total_cost, remaining_funds, percent_budget_target,
                   percent_budget_spent, target_cost, last_log.cost, roas_before, roas_after, gmv, income, roi]
            table.append(row)
    return table


def get_logs_table(logs, budget, headers=False):
    settings = GlobalSettings.get_settings()
    total_cost = 0
    budget_remaining = budget.to_spend
    table = []
    if headers:
        table = [['Dzień', 'Koszt całkowity', 'Pozostały budżet', '% wydanego budżetu', '% docelowy', 'Koszt docelowy',
                  'Koszt', 'ROAS przed', 'ROAS po', 'Obrót', 'Przychód netto', 'ROI']]
    for log in logs:
        row = [log.date.strftime('%Y-%m-%d')]
        if log.cost:
            total_cost += log.cost
            budget_remaining -= log.cost
        row.append(float(total_cost))
        row.append(float(budget_remaining))
        remaining_days = budget.date_to - log.date
        if remaining_days.days == 0:
            target_cost = float(budget_remaining)
        else:
            target_cost = float(budget_remaining / remaining_days.days)
        if budget_remaining < 0:
            target_cost = 0
        percent_budget_spent = float(round((total_cost / budget.to_spend), 4))
        percent_budget_target = float(round(((budget.to_spend / (budget.date_to.day + 1
                                                                 - budget.date_from.day)) / budget.to_spend)
                                            * (log.date.day + 1 - budget.date_from.day), 4))
        row.append("--") if log.cost is None else row.append(percent_budget_spent)
        row.append(percent_budget_target)
        row.append(round(target_cost, 2))
        row.append("--") if log.cost is None else row.append(float(log.cost))
        row.append("--") if log.roas_before is None else row.append(int(log.roas_before * 100))
        row.append("--") if log.roas_after is None else row.append(int(log.roas_after * 100))
        row.append(round(float(log.gmv) * float(settings.return_rate), 2)) if log.gmv else row.append("--")
        if log.income:
            net_income = round(float(log.income) * float(settings.return_rate) * float(settings.tax), 2)
            roi = round((net_income - float(log.cost)) / float(log.cost), 2) if log.cost else "--"
            row.extend([net_income, roi])
        else:
            row.extend(["--", "--"])
        table.append(row)
    return table


def get_logs_report(logs, headers=False):
    settings = GlobalSettings.objects.get(id=1)
    table = []
    if headers:
        table = [['Dzień', 'Koszt', 'GMV', 'Income', 'ROI']]
    for log in logs:
        row = [log.date.strftime('%Y-%m-%d')]
        row.append(0) if log.cost is None else row.append(float(log.cost))
        row.append(round(float(log.gmv) * float(settings.return_rate), 2)) if log.gmv else row.append(0)
        if log.income:
            net_income = round(float(log.income) * float(settings.return_rate) * float(settings.tax), 2)
            roi = round((net_income - float(log.cost)) / float(log.cost), 2) if log.cost else None
            row.extend([net_income, roi])
        else:
            row.extend([0, 0])
        table.append(row)
    return table


def get_campaign_logs_table(campaign_logs, headers=False):
    table = []
    if headers:
        table = [['Data', 'ROAS przed zmianą', 'ROAS po zmianie']]
    for log in campaign_logs:
        row = [log.date.strftime('%Y-%m-%d')]
        row.append("--") if log.roas_before is None else row.append(int(log.roas_before * 100))
        row.append("--") if log.roas_after is None else row.append(int(log.roas_after * 100))
        table.append(row)
    return table


def get_campaigns_table(campaigns):
    table = []
    for campaign in campaigns:
        table.append([campaign, campaign.account.account_name, campaign.strategy, campaign.roas_modifier,
                      campaign.manage_roas])
    return table


def calculate_last_day_off_target(table):
    last_day_cost = table[-1][6]
    last_day_target = table[-1][5]
    if type(last_day_cost) is str or type(last_day_target) is str:
        return "--"
    off_target = last_day_cost - last_day_target
    return round(off_target, 2)


def last_day_off_target_percent(table):
    last_day_cost = table[-1][6]
    last_day_target = table[-1][5]
    if last_day_target == 0:  # jeżeli budżet został przekroczony, każdy kolejny dzień to 200% kosztu docelowego
        return 200
    if type(last_day_cost) is str or type(last_day_target) is str:
        return "--"
    percent_off_target = last_day_cost / last_day_target
    return round(percent_off_target * 100, 1)


def get_campaign_group_table(campaign_group, date, headers=False):
    try:
        budget = campaign_group.budget_set.filter(date_from__lte=date, date_to__gte=date).get()
    except ObjectDoesNotExist:
        # print("Nie znaleziono budżetu dla bieżącej daty")
        return None
    logs = campaign_group.log_set.all().filter(date__gte=budget.date_from, date__lte=budget.date_to) \
        .order_by('date')
    if logs.exists():
        logs_table = get_logs_table(logs, budget, headers)
        return logs_table
    else:
        # print("Nie znaleziono logów w zakresie bieżącego budżetu")
        return None


def get_current_budget(strategy, date):
    budget = strategy.budget.filter(date_from__lte=date, date_to__gte=date)
    if budget.count() == 1:
        return budget.get()
    elif budget.count() > 1:
        logging.error(f"Błąd, strategia {strategy.name} ma budżety o pokrywających się datach!")


def budget_gap_checker(campaign_group, date_from, date_to):
    error = None
    last_budget = campaign_group.budget_set.all()
    if (date_to - date_from).days <= 0:
        error = f"Dzień roczpoczęcia budżetu musi następować po dniu jego zakończenia"
        return error
    if 0 < (date_to - date_from).days < 7:
        error = f"Okres budżetu nie może być mniejszy niż 7 dni"
        return error
    if last_budget.exists():
        budget = last_budget.order_by('date_to').reverse()[0]
        if (date_from - budget.date_to).days < 0:
            error = f"Grupa kampanii {campaign_group.name} ma już dodany budżet pokrywający się z " \
                    f"wybranym zakresem dat ({budget.date_from} - {budget.date_to}).\nPopraw nowy budżet " \
                    f"i zapisz ponownie."
        if (date_from - budget.date_to).days > 1:
            error = f"Próbujesz dodać budżet rozpoczynający się o więcej niż jeden dzień poźniej niż data końca " \
                    f"poprzedniego budżetu dodanego dla tej grupy kampanii. Przerwy między budżetami nie są dozwolone" \
                    f" - popraw datę rozpoczęcia nowego budżetu tak, aby następowała bezpośrednio po dniu" \
                    f" zakończenia poprzedniego ({budget.date_to}) i zapisz ponownie."
    return error


def add_day_to_last_budget_day(campaign_group):
    last_budget = campaign_group.budget_set.all()
    delta = timedelta(days=1)
    if last_budget.exists():
        budget = last_budget.order_by('-date_to')[0]
        new_date = budget.date_to + delta
        return new_date


def event_alert(message, account=None, campaign_group=None, strategy=None, send_now=False):
    print(message)
    if account:
        users = CustomUser.objects.filter(account=account)
    elif strategy:
        users = CustomUser.objects.filter(strategy=strategy)
    elif campaign_group:
        users = CustomUser.objects.filter(campaigngroup=campaign_group)
    else:
        users = CustomUser.objects.filter(id=1)
    alert = Alert.objects.create(date=datetime.now().date(), message=message)
    alert.user.set(users)
    alert.save()
    if send_now:
        message += message + '\n'
        subject = f'ROAS Manager - Alert niestandardowy'
        send_mail(subject, message, DEFAULT_FROM_EMAIL, [user.email for user in users])


def budget_double_check(budget, user):
    budget_owners = CustomUser.objects.filter(budget=budget)
    remaining_users = CustomUser.objects.all().exclude(id__in=budget_owners)
    if remaining_users.exists():
        selected_user = random.choice(remaining_users)
        message = f"""
        Sprawdź i zatwierdź nowy budżet utworzony przez użytkownika: {user.username}.
        Konto Google Ads: {budget.campaign_group.account.account_name}
        Grupa kampanii: {budget.campaign_group.name}
        Okres budżetu: {budget.date_from} - {budget.date_to}
        Wysokość budżetu: {budget.to_spend} zł
        Budżet możesz zatwierdzić tutaj: {APPLICATION_URL}{reverse('verify_budget')}
        """
        subject = "ROAS Manager | Zatwierdź nowy budżet"
        send_mail(subject, message, DEFAULT_FROM_EMAIL, [selected_user.email])
        budget.verifying_user = selected_user
        budget.save()
    else:
        print("Dodawanie nowego budżetu | tylko jeden użytkownik, dodatkowa weryfikacja pominięta")


def front_page_strategies_table(date):
    all_strategies = Strategy.objects.all().order_by('account', 'campaign_group')
    strategy_budgets = []
    for strategy in all_strategies:
        budget = get_current_budget(strategy, date)
        form = False
        if strategy.make_changes:
            form = True
        if budget:
            strategy_budgets.append([strategy, budget, form])
        else:
            strategy_budgets.append([strategy, 0, form])
    return strategy_budgets
