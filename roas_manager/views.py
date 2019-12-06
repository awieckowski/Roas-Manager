from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import render, redirect
from django.views.generic import View
from django.views.generic.edit import CreateView, UpdateView
from django.urls import reverse, reverse_lazy
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.forms.models import model_to_dict
from roas_manager.google_ads import get_strategies, get_campaign_groups, update_roas, set_roas_at_campaigns_wrapper, \
    update_url_suffix, get_roas_campaigns
from roas_manager.google_cloud_platform import save_gcp_data
from roas_manager.google_sheets import update_google_sheets, google_sheets_report
from roas_manager.google_ads import get_results_as_table
from roas_manager.tools import budget_double_check, get_overview_table, front_page_strategies_table, \
    add_day_to_last_budget_day, budget_gap_checker, calculate_last_day_off_target, get_campaigns_table, \
    last_day_off_target_percent, get_campaign_group_table, get_campaign_logs_table
from roas_manager.forms import *
from roas_manager.serializers import StrategySerializer, CampaignGroupSerializer, CampaignSerializer, BudgetSerializer
from RoasManager.settings import GOOGLE_SHEET_ID, CUSTOM_REPORT_SHEET_ID
from users.models import AlertSettings
from users.forms import AlertSettingsForm
from rest_framework import viewsets
from googleads import adwords
from googleads.errors import GoogleAdsServerFault, GoogleAdsError
from google.auth.exceptions import RefreshError
from datetime import datetime, timedelta
import logging


logger = logging.getLogger(__name__)


class DayOverview(LoginRequiredMixin, View):
    def get(self, request):
        today = (datetime.today()).date()
        today_str = today.strftime('%Y-%m-%d')
        overview_table = get_overview_table(today)
        return render(request, "overview.html", {'table': overview_table, 'today': today_str})

    def post(self, request):
        selected_date = request.POST.get('date_from')
        date = datetime.strptime(selected_date, '%Y-%m-%d').date()
        overview_table = get_overview_table(date)
        return render(request, "overview.html", {'table': overview_table, 'date': selected_date})


class Strategies(LoginRequiredMixin, View):
    def get(self, request):
        yesterday = (datetime.today() - timedelta(days=1)).date()
        strategy_budgets = front_page_strategies_table(yesterday)
        return render(request, "strategies.html", {'strategy_budgets': strategy_budgets, 'yesterday': yesterday})

    def post(self, request):
        selected_date = request.POST.get('date_from')
        date = datetime.strptime(selected_date, '%Y-%m-%d').date()
        strategy_budgets = front_page_strategies_table(date)
        return render(request, "strategies.html", {'strategy_budgets': strategy_budgets, 'date': date})


class StrategyView(LoginRequiredMixin, View):
    def get(self, request, strategy_id):
        strategy = Strategy.objects.get(id=strategy_id)
        account = Account.objects.filter(strategy=strategy).get()
        campaign_groups = account.campaigngroup_set.all()
        budgets = strategy.budget.all()
        initial = {'name': strategy.name, 'account': strategy.account, 'campaign_group': campaign_groups,
                   'make_changes': strategy.make_changes, 'strategy_id': strategy.strategy_id}
        form = StrategyForm(initial)
        ctx = {'strategy': strategy, 'budgets': budgets, 'campaign_groups': campaign_groups, 'form': form}
        return render(request, "strategy.html", ctx)

    def post(self, request, strategy_id):
        strategy = Strategy.objects.get(id=strategy_id)
        campaign_group = CampaignGroup.objects.get(id=request.POST.get('campaign_group'))
        budgets = campaign_group.budget_set.all()
        strategy.budget.set(budgets)
        strategy.campaign_group = campaign_group
        strategy.make_changes = bool(request.POST.get('make_changes'))
        strategy.save()
        return redirect(reverse('log', args=[strategy_id]))


class AddStrategy(LoginRequiredMixin, View):
    def get(self, request):
        strategy_form = StrategyForm()
        return render(request, "strategy_add.html", {'form': strategy_form})

    def post(self, request):
        account = Account.objects.get(id=request.POST.get("account"))
        strategy_form = StrategyForm()
        try:
            strategies_dict = get_strategies(account.account_number)  # pobierz strategie z konta
        except GoogleAdsServerFault:
            logger.error(f"Błąd API Google Ads podczas pobierania strategii z konta {account.account_name}")
            return redirect(reverse('error'))
        for strategy in strategies_dict:
            strategy_id = strategies_dict[strategy][0]
            strategy_status = strategies_dict[strategy][1]
            if Strategy.objects.filter(strategy_id=strategy_id).exists() or strategy_status != 'ENABLED':
                strategies_dict[strategy].append(False)  # służy do ustalenia, które mają być disabled w templatce
            else:
                strategies_dict[strategy].append(True)
        ctx = {'form': strategy_form, 'strategies': strategies_dict, 'account': account}
        return render(request, "strategy_add.html", ctx)


class StrategyViewSet(LoginRequiredMixin, viewsets.ModelViewSet):
    queryset = Strategy.objects.all().order_by('name')
    serializer_class = StrategySerializer


class AddCampaignGroup(LoginRequiredMixin, View):
    def get(self, request):
        campaign_group_form = CampaignGroupForm()
        return render(request, "campaign_group_add.html", {'form': campaign_group_form})

    def post(self, request):
        account_id = request.POST.get("account")
        account = Account.objects.get(id=account_id)
        account_number = account.account_number
        campaign_group_form = CampaignGroupForm()
        try:
            campaign_groups_dict = get_campaign_groups(account_number)  # pobierz grupy kampanii z konta
        except GoogleAdsServerFault:
            logger.error(f"Błąd API Google Ads podczas pobierania grupa kampanii z konta {account.account_name}")
            return redirect(reverse('error'))
        for cg in campaign_groups_dict:  # pobrane grupy kampanii zapisywane są via js/save_campaign_group_ajax.js
            if CampaignGroup.objects.filter(campaign_group_id=campaign_groups_dict[cg][0]).exists():
                campaign_groups_dict[cg].append(True)
            else:
                campaign_groups_dict[cg].append(False)
        ctx = {'form': campaign_group_form, 'account': account_number, 'account_id': account_id,
               'campaign_groups': campaign_groups_dict}
        return render(request, "campaign_group_add.html", ctx)


class CampaignGroupViewSet(LoginRequiredMixin, viewsets.ModelViewSet):
    queryset = CampaignGroup.objects.all().order_by('name')
    serializer_class = CampaignGroupSerializer


class EditCampaignGroup(LoginRequiredMixin, UpdateView):
    model = CampaignGroup
    form_class = CampaignGroupForm
    success_url = reverse_lazy('accounts')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = self.get_form()
        campaign_group = CampaignGroup.objects.get(id=self.object.id)
        context['campaign_group'] = campaign_group
        context['budgets'] = campaign_group.budget_set.all().order_by("date_from")
        return context


class EditBudget(LoginRequiredMixin, UpdateView):
    model = Budget
    fields = '__all__'
    success_url = reverse_lazy('strategies')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        budget = Budget.objects.get(id=self.object.id)
        context['form'] = self.get_form()
        context['campaign_group'] = budget.campaign_group
        return context


class AddBudget(LoginRequiredMixin, View):
    def get(self, request, campaign_group_id):
        campaign_group = CampaignGroup.objects.get(id=campaign_group_id)
        strategies = Strategy.objects.filter(campaign_group=campaign_group)
        day_after_last = add_day_to_last_budget_day(campaign_group)
        form = BudgetForm(initial={'campaign_group': campaign_group, 'date_from': day_after_last})
        ctx = {'strategies': strategies, 'strategies_count': strategies.count(), 'campaign_group': campaign_group,
               'form': form}
        return render(request, "budget_add.html", ctx)

    def post(self, request, campaign_group_id):
        campaign_group = CampaignGroup.objects.get(id=campaign_group_id)
        form = BudgetForm(request.POST)
        if form.is_valid():
            to_spend = form.cleaned_data['to_spend']
            date_from = form.cleaned_data['date_from']
            date_to = form.cleaned_data['date_to']
            error = budget_gap_checker(campaign_group, date_from, date_to)
            strategies = campaign_group.strategy_set.all()
            if error:
                ctx = {'strategies': strategies, 'strategies_count': strategies.count(),
                       'campaign_group': campaign_group, 'form': form, 'error': error}
                return render(request, "budget_add.html", ctx)
            new_budget = Budget.objects.create(to_spend=to_spend, date_from=date_from, date_to=date_to,
                                               campaign_group=campaign_group, verified=1)
            new_budget.user.set([request.user])
            [strat.budget.add(new_budget) for strat in strategies]
            budget_double_check(new_budget, request.user)
            return redirect(reverse('edit_campaign_group', args=[campaign_group_id]))
        else:
            strategies = Strategy.objects.filter(campaign_group=campaign_group)
            strategies_count = strategies.count()
            return render(request, "budget_add.html", {'strategies': strategies, 'strategies_count': strategies_count,
                                                       'campaign_group': campaign_group, 'form': form})


class VerifyBudgetView(LoginRequiredMixin, View):
    def get(self, request, ):
        budgets_to_verify = Budget.objects.filter(verifying_user=request.user, verified=1)
        return render(request, "budget_verify.html", {'budgets': budgets_to_verify})


class BudgetViewSet(LoginRequiredMixin, viewsets.ModelViewSet):
    queryset = Budget.objects.all().order_by('id')
    serializer_class = BudgetSerializer


class ViewLog(LoginRequiredMixin, View):
    def get(self, request, strategy_id):
        yesterday = (datetime.today() - timedelta(days=1)).date()
        strategy = Strategy.objects.get(id=strategy_id)
        campaign_group = strategy.campaign_group
        try:  # sprawdź czy dla tej strategii istnieje bieżący budżet
            budget = campaign_group.budget_set.filter(date_from__lte=yesterday, date_to__gte=yesterday).get()
        except (ObjectDoesNotExist, AttributeError):  # jeśli nie ma, wyświetl odpowiedni komunikat
            return render(request, "log.html", {'campaign_group': campaign_group, 'strategy': strategy})
        logs_table = get_campaign_group_table(campaign_group, yesterday)
        if logs_table:  # sprawdź, czy dla tej strategii istnieją logi
            if budget.date_to == yesterday:
                off_target = '--'
                off_target_percent = '--'
            else:
                off_target = calculate_last_day_off_target(logs_table)
                off_target_percent = last_day_off_target_percent(logs_table)
            if logs_table[-1][0] == yesterday.strftime('%Y-%m-%d'):
                yesterday_row = logs_table[-1]
            else:
                yesterday_row = None
            user_strategies = request.user.strategy_set.all().order_by('account')
            ctx = {'table': logs_table, 'budget': budget, 'strategy': strategy, 'last_day_off_target': off_target,
                   'last_day_off_target_percent': off_target_percent, 'campaign_group': campaign_group,
                   'sheet_id': GOOGLE_SHEET_ID, 'yesterday_row': yesterday_row, 'user_strategies': user_strategies}
            return render(request, "log.html", ctx)
        else:
            return render(request, "log.html", {'campaign_group': campaign_group, 'strategy': strategy,
                                                'budget': budget})

    def post(self, request, strategy_id):
        selected_date = request.POST.get('date_from')
        date = datetime.strptime(selected_date, '%Y-%m-%d')
        strategy = Strategy.objects.get(id=strategy_id)
        campaign_group = strategy.campaign_group
        try:  # sprawdź czy dla tej strategii istnieje bieżący budżet
            budget = campaign_group.budget_set.filter(date_from__lte=date, date_to__gte=date).get()
        except (ObjectDoesNotExist, AttributeError):  # jeśli nie ma, wyświetl odpowiedni komunikat
            return render(request, "log.html", {'campaign_group': campaign_group, 'strategy': strategy,
                                                'date': selected_date})
        logs_table = get_campaign_group_table(campaign_group, date)
        if logs_table:  # sprawdź, czy dla tej strategii istnieją logi
            user_strategies = request.user.strategy_set.all().order_by('account')
            ctx = {'table': logs_table, 'budget': budget, 'strategy': strategy, 'campaign_group': campaign_group,
                   'sheet_id': GOOGLE_SHEET_ID, 'user_strategies': user_strategies, 'date': selected_date}
            return render(request, "log.html", ctx)
        else:
            return render(request, "log.html", {'campaign_group': campaign_group, 'strategy': strategy,
                                                'budget': budget, 'date': selected_date})


class ViewAccounts(LoginRequiredMixin, View):
    def get(self, request):
        accounts = Account.objects.all().order_by('account_name')
        campaign_groups = CampaignGroup.objects.all().order_by('account')
        return render(request, "accounts.html", {'accounts': accounts, 'campaign_groups': campaign_groups})


class AddAccount(LoginRequiredMixin, CreateView):
    model = Account
    fields = ['account_number', 'account_name']
    success_url = reverse_lazy('accounts')

    def form_valid(self, form):
        obj = form.save(commit=True)
        obj.user.set([self.request.user])
        return super(AddAccount, self).form_valid(form)


class EditAccount(LoginRequiredMixin, UpdateView):
    model = Account
    fields = ['account_number', 'account_name', 'user']
    success_url = reverse_lazy('accounts')


class CampaignGroupsPerformance(LoginRequiredMixin, View):
    def get(self, request):
        yesterday = datetime.today() - timedelta(days=1)
        form = GetCostClicksForm(initial={'date_from': yesterday, 'date_to': yesterday, 'campaign_group': 'checked'})
        campaign_groups = CampaignGroup.objects.all()
        return render(request, 'get_report.html', {'form': form, 'campaign_groups': campaign_groups})

    def post(self, request):
        form = GetCostClicksForm(request.POST)
        if form.is_valid():
            report_types = request.POST.getlist('report_type')
            campaign_group_ids = request.POST.getlist('campaign_group')
            date_from = form.cleaned_data["date_from"]
            date_to = form.cleaned_data["date_to"]
            account = form.cleaned_data["account"]
            overwrite = request.POST.get('overwrite')
            export_report = request.POST.getlist('google_sheets')
            campaign_groups = CampaignGroup.objects.all().filter(account=account, id__in=campaign_group_ids)
            cost_results = {}
            income_results = {}
            if 'cost' in report_types:
                cost_results = get_results_as_table(account, campaign_groups, date_from, date_to)
            if 'income' in report_types:
                try:
                    if overwrite:
                        income_results = save_gcp_data([account], date_from, date_to, campaign_groups=campaign_groups,
                                                       overwrite=True)
                    else:
                        income_results = save_gcp_data([account], date_from, date_to, campaign_groups=campaign_groups)

                except RefreshError:  # Błąd w sytuacji przedawnienia klucza
                    logger.error("Błąd API podczas pobierania danych z Big Query")
                    return redirect(reverse('error'))
            if export_report:
                update_google_sheets([account])
            return render(request, 'get_report.html', {'form': form, 'cost_results': cost_results,
                                                       'income_results': income_results, 'report_types': report_types})
        else:
            campaign_groups = CampaignGroup.objects.all()
            return render(request, 'get_report.html', {'form': form, 'campaign_groups': campaign_groups})


class SetStrategyRoas(LoginRequiredMixin, View):
    def get(self, request):
        set_roas_form = SetRoasForm()
        campaign_groups = CampaignGroup.objects.all()
        return render(request, "set_strategy_roas.html", {'form': set_roas_form, 'campaign_groups': campaign_groups})

    def post(self, request):
        override_check = not request.POST.getlist('override_check')
        campaign_group_ids = request.POST.getlist('campaign_group')
        campaign_groups = CampaignGroup.objects.filter(id__in=campaign_group_ids)
        strategies = []
        for cg in campaign_groups:
            [strategies.append(strategy) for strategy in Strategy.objects.filter(campaign_group=cg)]
        account = Account.objects.get(id=request.POST.get('account'))
        adwords_client = adwords.AdWordsClient.LoadFromStorage()
        adwords_client.SetClientCustomerId(account.account_number)
        try:
            result = update_roas(strategies, account, adwords_client, dry_run=True, override_check=override_check)
            logger.info(f"{request.user.username} | Uruchomiona ręczna aktualizacja ROAS na poziomie strategii")
        except GoogleAdsError:
            logger.error("Błąd API podczas próby ręcznej aktualizacji ROAS na poziomie strategii")
            return redirect(reverse('error'))
        return render(request, "set_strategy_roas.html", {'campaign_groups': campaign_groups, 'result': result})


class SetCampaignRoas(LoginRequiredMixin, View):
    def get(self, request):
        set_roas_form = SetRoasForm()
        strategies = Strategy.objects.all()
        return render(request, "set_campaign_roas.html", {'form': set_roas_form, 'strategies': strategies})

    def post(self, request):
        override_check = not request.POST.getlist('override_check')
        strategies = Strategy.objects.filter(id__in=request.POST.getlist('strategy'))
        client = adwords.AdWordsClient.LoadFromStorage()
        account = Account.objects.get(id=request.POST.get("account"))
        try:
            result = set_roas_at_campaigns_wrapper(client, accounts=[account], strategies=strategies,
                                                   override_check=override_check,)
            logger.info(f"{request.user.username} | Uruchomiona ręczna aktualizacja ROAS na poziomie kampanii")
            return render(request, "set_campaign_roas.html", {'result': result})
        except GoogleAdsError:
            logger.error("Błąd API podczas próby ręcznej aktualizacji ROAS na poziomie kampanii")
            return redirect(reverse('error'))


class SetUrlSuffix(LoginRequiredMixin, View):
    def get(self, request):
        form = StrategyForm()
        return render(request, "set_suffix.html", {'form': form})

    def post(self, request):
        account_id = request.POST.get("account")
        account = Account.objects.get(id=account_id)
        adwords_client = adwords.AdWordsClient.LoadFromStorage()
        results = update_url_suffix(adwords_client, account)
        if results:
            count = len(results)
        else:
            count = 0
        return render(request, "set_suffix_post.html", {'results': results, 'account': account, 'count': count})


class SettingsPage(LoginRequiredMixin, View):
    def get(self, request):
        current_settings = GlobalSettings.get_settings()
        form = GlobalSettingsForm(initial={'tax': current_settings.tax, 'return_rate': current_settings.return_rate})
        alert_settings, created = AlertSettings.objects.get_or_create(user=request.user)
        settings_as_dict = model_to_dict(alert_settings)
        alert_form = AlertSettingsForm(initial=settings_as_dict)
        ctx = {'tax_rate': current_settings.tax, 'return_rate': current_settings.return_rate, 'form': form,
               'alert_form': alert_form}
        return render(request, "settings.html", ctx)

    def post(self, request):
        form = GlobalSettingsForm(request.POST)
        if form.is_valid():
            messages.success(request, 'Zmiany zostały zapisane')
            current_settings = GlobalSettings.objects.all()
            current_settings.update(tax=form.cleaned_data['tax'], return_rate=form.cleaned_data['return_rate'])
        return render(request, "settings.html", {'form': form})


class AlertsSettingsView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    model = AlertSettings
    success_message = 'Zmiany zostały zapisane.'
    fields = ['cost_threshold_upper', 'cost_threshold_lower', 'roi_threshold', 'campaign_group_coverage',
              'budget_depleted', 'no_new_budget']
    success_url = reverse_lazy('settings')


class CampaignsView(LoginRequiredMixin, View):
    def get(self, request):
        campaigns_table = []
        campaigns = Campaign.objects.all().order_by('account').order_by('strategy').order_by('name')
        if campaigns.exists():
            campaigns_table = get_campaigns_table(campaigns)
        return render(request, "campaigns.html", {'campaigns_table': campaigns_table})


class CampaignEditView(LoginRequiredMixin, UpdateView):
    model = Campaign
    form_class = CampaignForm
    success_url = reverse_lazy('campaigns')

    def get_context_data(self, **kwargs):
        time_range = (datetime.today() - timedelta(days=30)).date()
        context = super().get_context_data(**kwargs)
        context['form'] = self.get_form()
        campaign = Campaign.objects.get(id=self.object.id)
        logs = CampaignRoasLog.objects.filter(campaign=campaign, date__gte=time_range)
        context['table'] = get_campaign_logs_table(logs)
        return context


class AddCampaignView(LoginRequiredMixin, View):
    def get(self, request):
        form = CampaignForm
        campaign_groups = CampaignGroup.objects.all()
        return render(request, "campaign_add.html", {'form': form, 'campaign_groups': campaign_groups})

    def post(self, request):
        campaign_groups = CampaignGroup.objects.all()
        form = CampaignForm
        account = Account.objects.get(id=request.POST.get("account"))
        try:
            campaigns = get_roas_campaigns(account.account_number)
        except GoogleAdsServerFault:
            logger.error(f"{request.user.username} | Błąd API Google Ads podczas próby pobrania kampanii")
            return redirect(reverse('error'))
        if campaigns:
            for campaign in campaigns:
                if Campaign.objects.filter(campaign_id=campaigns[campaign][0]).exists():
                    campaigns[campaign].append(False)
                else:
                    campaigns[campaign].append(True)
        ctx = {'form': form, 'campaign_groups': campaign_groups, 'campaigns': campaigns, 'account_id': account.id}
        return render(request, "campaign_add.html", ctx)


class CampaignViewSet(LoginRequiredMixin, viewsets.ModelViewSet):
    queryset = Campaign.objects.all().order_by('name')
    serializer_class = CampaignSerializer


class ErrorView(LoginRequiredMixin, View):
    def get(self, request):
        return render(request, "error.html")


class CampaignGroupsReportView(LoginRequiredMixin, View):
    def get(self, request):
        yesterday = datetime.today() - timedelta(days=1)
        form = GetCostClicksForm(initial={'date_from': yesterday, 'date_to': yesterday, 'campaign_group': 'checked'})
        campaign_groups = CampaignGroup.objects.all()
        return render(request, 'report_campaign_groups.html', {'form': form, 'campaign_groups': campaign_groups})

    def post(self, request):
        form = GetCostClicksForm(request.POST)
        if form.is_valid():
            report_types = request.POST.getlist('report_type')
            campaign_group_ids = request.POST.getlist('campaign_group')
            date_from = form.cleaned_data["date_from"]
            date_to = form.cleaned_data["date_to"]
            account = form.cleaned_data["account"]
            campaign_groups = CampaignGroup.objects.all().filter(account=account, id__in=campaign_group_ids)
            if 'cost' in report_types:
                get_results_as_table(account, campaign_groups, date_from, date_to)
            if 'income' in report_types:
                try:
                    save_gcp_data([account], date_from, date_to, campaign_groups=campaign_groups, overwrite=True)
                except RefreshError:  # Błąd w sytuacji przedawnienia klucza
                    logger.error(f"{request.user.username} | Błąd API podczas pobierania danych z Big Query")
                    return redirect(reverse('error'))
            google_sheets_report(campaign_groups, date_from, date_to)
            success = True
            return render(request, 'report_campaign_groups.html', {'success': success, 'sheet': CUSTOM_REPORT_SHEET_ID})
        else:
            campaign_groups = CampaignGroup.objects.all()
            return render(request, 'report_campaign_groups.html', {'form': form, 'campaign_groups': campaign_groups})


class AlertsView(LoginRequiredMixin, View):
    def get(self, request):
        today = datetime.today().date()
        today_str = today.strftime('%Y-%m-%d')
        user_alerts = Alert.objects.filter(date=today, user=request.user)
        all_alerts = Alert.objects.filter(date=today)
        user_alerts_count = user_alerts.count()
        all_alerts_count = all_alerts.count()
        ctx = {'today': today_str, 'alerts': all_alerts, 'all_alerts_count': all_alerts_count,
               'user_alerts_count': user_alerts_count}
        return render(request, 'alerts.html', ctx)

    def post(self, request):
        selected_date = request.POST.get('date_from')
        date = datetime.strptime(selected_date, '%Y-%m-%d').date()
        user_alerts = Alert.objects.filter(date=selected_date, user=request.user)
        all_alerts = Alert.objects.filter(date=selected_date)
        user_alerts_count = user_alerts.count()
        all_alerts_count = all_alerts.count()
        ctx = {'date': date, 'alerts': all_alerts, 'all_alerts_count': all_alerts_count,
               'user_alerts_count': user_alerts_count}
        return render(request, 'alerts.html', ctx)
