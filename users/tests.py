import decimal
from datetime import datetime, timedelta
from calendar import monthrange
from django.test import TestCase, Client
from users.models import CustomUser
from roas_manager.models import Strategy, CampaignGroup, Log, Budget, Account
from roas_manager.tools import calculate_target_cost, calculate_costs_difference
from parameterized import parameterized
from freezegun import freeze_time


def convert_decimal_table_to_float(table):
    converted_table = []
    for row in table:
        converted_row = []
        for cell in row:
            if isinstance(cell, decimal.Decimal):
                converted_row.append(float(cell))
            else:
                converted_row.append(cell)
        converted_table.append(converted_row)
    return converted_table


class LoggingUsers(TestCase):
    def setUp(self):
        CustomUser.objects.create_user(username='TestUser', email='roas.manager@allegro.pl',
                                       password='j4uSYD4z0jdF8bFjydHa')
        user = CustomUser.objects.latest('id')
        account = Account.objects.create(account_name="TestAccount", account_number="159-510-9835")
        user.account_set.add(account)

        user_2 = CustomUser.objects.create_user(username='TestUser2', password='j4uSYD4z0jdF8bFjydHa')
        account_2 = Account.objects.create(account_name="TestAccount2", account_number="159-510-9836")
        user_2.account_set.add(account_2)

        campaign_group_a = CampaignGroup.objects.create(name='Test_CG_A | Cost 1k / day', campaign_group_id='A')
        user.campaigngroup_set.add(campaign_group_a)
        account.campaigngroup_set.add(campaign_group_a)
        campaign_group_a.account = account

        campaign_group_b = CampaignGroup.objects.create(name='Test_CG_B | Cost 2k / day', campaign_group_id='B')
        user.campaigngroup_set.add(campaign_group_b)
        account.campaigngroup_set.add(campaign_group_b)
        campaign_group_b.account = account

        campaign_group_c = CampaignGroup.objects.create(name='Test_CG_C | Cost 0.5k / day', campaign_group_id='C')
        user.campaigngroup_set.add(campaign_group_c)
        account.campaigngroup_set.add(campaign_group_c)
        campaign_group_c.account = account

        campaign_group_1 = CampaignGroup.objects.create(name='Test_CG_1 | Budget not added', campaign_group_id='1')
        user_2.campaigngroup_set.add(campaign_group_1)
        account_2.campaigngroup_set.add(campaign_group_1)

        campaign_group_2 = CampaignGroup.objects.create(name='Test_CG_2 | Last day log missing', campaign_group_id='2')
        user_2.campaigngroup_set.add(campaign_group_2)
        account_2.campaigngroup_set.add(campaign_group_2)

        strategy_a = Strategy.objects.create(name='Test_Strat_A | Cost 1k / day', strategy_id='A', make_changes=True)
        user.strategy_set.add(strategy_a)
        account.strategy_set.add(strategy_a)
        campaign_group_a.strategy_set.add(strategy_a)

        strategy_b = Strategy.objects.create(name='Test_Strat_B | Cost 2k / day', strategy_id='B', make_changes=True)
        user.strategy_set.add(strategy_b)
        account.strategy_set.add(strategy_b)
        campaign_group_b.strategy_set.add(strategy_b)

        strategy_c = Strategy.objects.create(name='Test_Strat_C | Cost 0.5k / day', strategy_id='C', make_changes=True)
        user.strategy_set.add(strategy_c)
        account.strategy_set.add(strategy_c)
        campaign_group_c.strategy_set.add(strategy_c)

        strategy_1 = Strategy.objects.create(name='Test_Strat_1 | No budget added', strategy_id='1', make_changes=True)
        user_2.strategy_set.add(strategy_1)
        account_2.strategy_set.add(strategy_1)
        campaign_group_1.strategy_set.add(strategy_1)

        strategy_2 = Strategy.objects.create(name='Test_Strat_2 | Last day log missing', strategy_id='2',
                                             make_changes=True)
        user_2.strategy_set.add(strategy_2)
        account_2.strategy_set.add(strategy_2)
        campaign_group_2.strategy_set.add(strategy_2)

        logs_a = []
        logs_b = []
        logs_c = []
        logs_1 = []
        logs_2 = []

        dates = ['2020-01-01', '2020-01-02', '2020-05-14', '2020-02-29']
        for date in dates:
            with freeze_time(date):
                yesterday = (datetime.today() - timedelta(days=1)).date()
                yesterday_month = yesterday.month
                yesterday_year = yesterday.year
                days_in_month = monthrange(yesterday_year, yesterday_month)[1]
                budget_from = datetime(yesterday_year, yesterday_month, 1)
                budget_to = datetime(yesterday_year, yesterday_month, days_in_month)
                to_spend = 1000 * days_in_month
                budget_a = Budget.objects.create(to_spend=to_spend, date_from=budget_from, date_to=budget_to)
                budget_b = Budget.objects.create(to_spend=to_spend, date_from=budget_from, date_to=budget_to)
                budget_c = Budget.objects.create(to_spend=to_spend, date_from=budget_from, date_to=budget_to)
                budget_1 = Budget.objects.create(to_spend=to_spend, date_from=budget_from, date_to=budget_to)
                user.budget_set.add(budget_a)
                user.budget_set.add(budget_b)
                user.budget_set.add(budget_c)
                user_2.budget_set.add(budget_1)
                campaign_group_a.budget_set.add(budget_a)
                campaign_group_b.budget_set.add(budget_b)
                campaign_group_c.budget_set.add(budget_c)
                campaign_group_2.budget_set.add(budget_1)
                budget_a.strategy_set.add(strategy_a)
                budget_b.strategy_set.add(strategy_b)
                budget_c.strategy_set.add(strategy_c)
                budget_1.strategy_set.add(strategy_2)
                budget_days = (yesterday - budget_a.date_from.date()).days
            for day in range(budget_days+1):  # dodaj tyle logów ile było dni od początku okresu budżetowego
                with freeze_time(date):
                    date = datetime(yesterday_year, yesterday_month, day + 1)
                    log_a = Log.objects.create(date=date, cost=1000, clicks=10000, roas_before=10, roas_after=10,
                                             gmv=20000, income=2000, transactions=200)
                    log_b = Log.objects.create(date=date, cost=2000, clicks=20000, roas_before=10, roas_after=10,
                                              gmv=20000, income=2000, transactions=200)
                    log_c = Log.objects.create(date=date, cost=500, clicks=20000, roas_before=10, roas_after=10,
                                               gmv=20000, income=2000, transactions=200)
                    log_1 = Log.objects.create(date=date, cost=1000, clicks=10000, roas_before=10, roas_after=10,
                                               gmv=20000, income=2000, transactions=200)
                    log_2 = Log.objects.create(date=date, cost=1000, clicks=10000, roas_before=10, roas_after=10,
                                               gmv=20000, income=2000, transactions=200)
                    log_a.refresh_from_db()
                    log_b.refresh_from_db()
                    log_c.refresh_from_db()
                    log_1.refresh_from_db()
                    log_2.refresh_from_db()

                    logs_a.append(log_a)
                    logs_b.append(log_b)
                    logs_c.append(log_c)
                    logs_1.append(log_1)
                    logs_2.append(log_2)

        campaign_group_a.log_set.set(logs_a)
        campaign_group_b.log_set.set(logs_b)
        campaign_group_c.log_set.set(logs_c)
        campaign_group_1.log_set.set(logs_1)
        campaign_group_2.log_set.set(logs_2)

        for day in dates:
            date = datetime.strptime(day, '%Y-%m-%d')
            day_before = (date - timedelta(days=1)).date()
            campaign_group_2.log_set.filter(date=day_before).delete()

    def test_users_not_logged_in_get_302(self):
        c = Client()
        response = c.get('/')
        self.assertEqual(response.status_code, 302)

    def test_can_log_in(self):
        c = Client()
        response = c.post('/accounts/login/', {'username': 'TestUser', 'password': 'j4uSYD4z0jdF8bFjydHa'}, follow=True)
        self.assertTrue(response.context['user'].is_authenticated)

    def test_not_existing_user_cant_log_in(self):
        c = Client()
        response = c.post('/accounts/login/', {'username': 'TestUserr', 'password': 'j4uSYD4z0jdF8bFjydHa'},
                          follow=True)
        self.assertFalse(response.context['user'].is_authenticated)

    @parameterized.expand([
        ("2020-05-14", {
            'Test_Strat_A | Cost 1k / day': [13000, 18000, 0.4194, 0.4194, 1000, 1000, 1],
            'Test_Strat_B | Cost 2k / day': [26000, 5000, 0.4194, 0.8387, 277.78, 2000, 0],
            'Test_Strat_C | Cost 0.5k / day': [6500, 24500, 0.4194, 0.2097, 1361.11, 500, 3],
                }),
    ])
    def test_main_page_table_complete_strategies(self, test_date, table_correct_results):
        c = Client()
        with freeze_time(test_date):
            c.login(username='TestUser', password='j4uSYD4z0jdF8bFjydHa')
            response = c.get('/')
            yesterday = (datetime.today() - timedelta(days=1)).date()
        correct_table = []
        for row_key in table_correct_results:
            strategy = Strategy.objects.get(name=row_key)
            account = Account.objects.get(strategy=strategy).account_name
            results = table_correct_results[row_key]
            new_row = [strategy, account, results[0], results[1], results[2], results[3], results[4], results[5],
                       1000, 1000, 20000, 2000, results[6]]
            correct_table.append(new_row)
        table = response.context['table']
        converted_table = convert_decimal_table_to_float(table)
        strategy_1 = Strategy.objects.get(name='Test_Strat_1 | No budget added')
        strategy_2 = Strategy.objects.get(name='Test_Strat_2 | Last day log missing')
        account_1 = Account.objects.get(strategy=strategy_1).account_name
        account_2 = Account.objects.get(strategy=strategy_2).account_name
        self.assertEqual(correct_table[0], converted_table[0])
        self.assertEqual(correct_table[1], converted_table[1])
        self.assertEqual(correct_table[2], converted_table[2])
        self.assertEqual([strategy_1, account_1, None, None, None, None, None, None, None, None, None, None], table[3])
        self.assertEqual([strategy_2, account_2, '--', '--', '--', '--', '--', '--', '--', '--', '--', '--'], table[4])

    @parameterized.expand([
        ("2020-05-14", 31000),
        ("2020-02-29", 29000),
        ("2020-01-01", 31000),
    ])
    def test_strategies_view_table_has_correct_values(self, test_date, budget_to_spend):
        c = Client()
        with freeze_time(test_date):
            yesterday = (datetime.today() - timedelta(days=1)).date()
            c.login(username='TestUser', password='j4uSYD4z0jdF8bFjydHa')
            response = c.get('/strategies/')
        table = response.context['strategy_budgets']
        test_strategy_a = Strategy.objects.get(name="Test_Strat_A | Cost 1k / day")
        test_strategy_b = Strategy.objects.get(name="Test_Strat_B | Cost 2k / day")
        test_strategy_c = Strategy.objects.get(name="Test_Strat_C | Cost 0.5k / day")
        test_strategy_1 = Strategy.objects.get(name="Test_Strat_1 | No budget added")
        test_strategy_2 = Strategy.objects.get(name="Test_Strat_2 | Last day log missing")
        # import pdb; pdb.set_trace()
        self.assertEqual([table[0][0], table[0][1].to_spend, table[0][2]], [test_strategy_a, budget_to_spend, True])
        self.assertEqual([table[1][0], table[1][1].to_spend, table[1][2]], [test_strategy_b, budget_to_spend, True])
        self.assertEqual([table[2][0], table[2][1].to_spend, table[2][2]], [test_strategy_c, budget_to_spend, True])
        self.assertEqual([table[3][0], table[3][1], table[3][2]], [test_strategy_1, 0, True])
        self.assertEqual([table[4][0], table[4][1].to_spend, table[4][2]], [test_strategy_2, budget_to_spend, True])

    @parameterized.expand([
        ("2020-01-01", 'Test_Strat_A | Cost 1k / day',
         ['2019-12-01', 1000.0, 30000.0, 0.0323, 0.0323, 1000.0, 1000.0, 1000, 1000, 20000.0, 2000.0, 1.0],
         ['2019-12-31', 31000.0, 0.0, 1.0, 1.0, 0.0, 1000.0, 1000, 1000, 20000.0, 2000.0, 1.0], '--', '--'),
        ("2020-01-02", 'Test_Strat_A | Cost 1k / day',
         ['2020-01-01', 1000.0, 30000.0, 0.0323, 0.0323, 1000.0, 1000.0, 1000, 1000, 20000.0, 2000.0, 1.0],
         ['2020-01-01', 1000.0, 30000.0, 0.0323, 0.0323, 1000.0, 1000.0, 1000, 1000, 20000.0, 2000.0, 1.0], 0, 100),
        ("2020-02-29", 'Test_Strat_A | Cost 1k / day',
         ['2020-02-01', 1000.0, 28000.0, 0.0345, 0.0345, 1000.0, 1000.0, 1000, 1000, 20000.0, 2000.0, 1.0],
         ['2020-02-28', 28000.0, 1000.0, 0.9655, 0.9655, 1000.0, 1000.0, 1000, 1000, 20000.0, 2000.0, 1.0], 0, 100),
        ("2020-05-14", 'Test_Strat_A | Cost 1k / day',
         ['2020-05-01', 1000.0, 30000.0, 0.0323, 0.0323, 1000.0, 1000.0, 1000, 1000, 20000.0, 2000.0, 1.0],
         ['2020-05-13', 13000.0, 18000.0, 0.4194, 0.4194, 1000.0, 1000.0, 1000, 1000, 20000.0, 2000.0, 1.0], 0, 100),
        ("2020-05-14", 'Test_Strat_B | Cost 2k / day',
         ['2020-05-01', 2000.0, 29000.0, 0.0645, 0.0323, 966.67, 2000.0, 1000, 1000, 20000.0, 2000.0, 0.0],
         ['2020-05-13', 26000.0, 5000.0, 0.8387, 0.4194, 277.78, 2000.0, 1000, 1000, 20000.0, 2000.0, 0.0], 1722.22, 720),
        ("2020-05-14", 'Test_Strat_C | Cost 0.5k / day',
         ['2020-05-01', 500.0, 30500.0, 0.0161, 0.0323, 1016.67, 500.0, 1000, 1000, 20000.0, 2000.0, 3.0],
         ['2020-05-13', 6500.0, 24500.0, 0.2097, 0.4194, 1361.11, 500.0, 1000, 1000, 20000.0, 2000.0, 3.0], -861.11, 36.7),
        ("2020-05-14", 'Test_Strat_2 | Last day log missing',
         ['2020-05-01', 1000.0, 30000.0, 0.0323, 0.0323, 1000.0, 1000.0, 1000, 1000, 20000.0, 2000.0, 1.0],
         ['2020-05-12', 12000.0, 19000.0, 0.3871, 0.3871, 1000.0, 1000.0, 1000, 1000, 20000.0, 2000.0, 1.0], 0, 100),


    ])
    def test_log_for_strategy_table_has_correct_values(self, test_date, strategy_name, table_first_row, table_last_row,
                                                       off_target, off_target_percent):
        c = Client()
        strategy = Strategy.objects.get(name=strategy_name)
        with freeze_time(test_date):
            yesterday = (datetime.today() - timedelta(days=1)).date()
            c.login(username='TestUser', password='j4uSYD4z0jdF8bFjydHa')
            response = c.get(f'/strategy/{strategy.id}/')
        table = response.context['table']
        converted_table = convert_decimal_table_to_float(table)
        # import pdb; pdb.set_trace()
        self.assertEqual(converted_table[0], table_first_row)
        self.assertEqual(converted_table[-1], table_last_row)
        self.assertEqual(response.context['last_day_off_target'], off_target)
        self.assertEqual(response.context['last_day_off_target_percent'], off_target_percent)

    @parameterized.expand([
        ("2020-01-01", 'Test_Strat_1 | No budget added'),
        ("2020-05-14", 'Test_Strat_1 | No budget added'),
    ])
    def test_no_table_if_budget_missing(self, test_date, strategy_name):
        c = Client()
        strategy = Strategy.objects.get(name=strategy_name)
        with freeze_time(test_date):
            yesterday = (datetime.today() - timedelta(days=1)).date()
            c.login(username='TestUser', password='j4uSYD4z0jdF8bFjydHa')
            response = c.get(f'/strategy/{strategy.id}/')
        self.assertEqual(response.context['strategy'], strategy)
        with self.assertRaises(KeyError):
            response.context['table']

    @parameterized.expand([
        ("2020-01-01", 'TestUser', 'Test_CG_A | Cost 1k / day', 1),
        ("2020-02-29", 'TestUser', 'Test_CG_A | Cost 1k / day', 1)
    ])
    def test_cost_threshold_check(self, test_date, username, campaign_group_name, result):
        with freeze_time(test_date):
            user = CustomUser.objects.get(username=username)
            campaign_group = CampaignGroup.objects.get(name=campaign_group_name)
            yesterday = (datetime.today() - timedelta(days=1)).date()
            budget = campaign_group.budget_set.filter(date_from__gte=yesterday, date_to__lte=yesterday)
            yesterday_log = campaign_group.log_set.filter(date=yesterday).first()
            check_result = user.check_cost_threshold(campaign_group, budget, yesterday_log)
        self.assertEqual(check_result, result)

    @parameterized.expand([
        ("2020-01-01", 'Test_CG_A | Cost 1k / day', 1000),
        ("2020-01-02", 'Test_CG_A | Cost 1k / day', 1000),
        ("2020-05-14", 'Test_CG_A | Cost 1k / day', 1000),
        ("2020-02-29", 'Test_CG_A | Cost 1k / day', 1000),
        ("2020-01-01", 'Test_CG_B | Cost 2k / day', 2000),  # w pierwszy dzień nowego okresu target cost = actual cost
        ("2020-01-02", 'Test_CG_B | Cost 2k / day', 967),
        ("2020-05-14", 'Test_CG_B | Cost 2k / day', 278),
        ("2020-02-29", 'Test_CG_B | Cost 2k / day', 0),
        ("2020-01-01", 'Test_CG_C | Cost 0.5k / day', 500),
        ("2020-01-02", 'Test_CG_C | Cost 0.5k / day', 1017),
        ("2020-05-14", 'Test_CG_C | Cost 0.5k / day', 1361),
        ("2020-02-29", 'Test_CG_C | Cost 0.5k / day', 15000),
    ])
    def test_target_cost_check(self, test_date, campaign_group_name, result):
        campaign_group = CampaignGroup.objects.get(name=campaign_group_name)
        with freeze_time(test_date):
            target_cost = calculate_target_cost(campaign_group)
        self.assertEqual(round(target_cost, 0), result)

    @parameterized.expand([
        ("2020-01-01", 'Test_CG_A | Cost 1k / day', 1000, 1),
        ("2020-01-01", 'Test_CG_A | Cost 1k / day', 2000, 0.5),
        ("2020-01-01", 'Test_CG_A | Cost 1k / day', 500, 2),
        ("2020-01-01", 'Test_CG_B | Cost 2k / day', 1000, 2),
        ("2020-01-01", 'Test_CG_B | Cost 2k / day', 2000, 1),
        ("2020-01-01", 'Test_CG_B | Cost 2k / day', 500, 4),
        ("2020-01-01", 'Test_CG_C | Cost 0.5k / day', 1000, 0.5),
        ("2020-01-01", 'Test_CG_C | Cost 0.5k / day', 2000, 0.25),
        ("2020-01-01", 'Test_CG_C | Cost 0.5k / day', 500, 1),
        ("2020-05-14", 'Test_CG_C | Cost 0.5k / day', 1361, 0.37),

    ])
    def test_cost_difference_check(self, test_date, campaign_group_name, target_cost, result):
        campaign_group = CampaignGroup.objects.get(name=campaign_group_name)
        with freeze_time(test_date):
            cost_difference = round(float(calculate_costs_difference(campaign_group, target_cost)), 2)
        self.assertEqual(cost_difference, result)

    @parameterized.expand([
        ("2020-01-01", 'Test_CG_A | Cost 1k / day', 1000),
        ("2020-01-02", 'Test_CG_A | Cost 1k / day', 1000),
        ("2020-01-01", 'Test_CG_B | Cost 2k / day', 2000),
        ("2020-01-02", 'Test_CG_B | Cost 2k / day', 966.67),
        ("2020-01-01", 'Test_CG_C | Cost 0.5k / day', 500),
        ("2020-01-02", 'Test_CG_C | Cost 0.5k / day', 1016.67),
        ("2020-05-14", 'Test_CG_C | Cost 0.5k / day', 1361.11),

    ])
    def test_calculate_target_cost_check(self, test_date, campaign_group_name, correct_target_cost):
        campaign_group = CampaignGroup.objects.get(name=campaign_group_name)
        with freeze_time(test_date):
            target_cost = round(float(calculate_target_cost(campaign_group)), 2)
        self.assertAlmostEqual(target_cost, correct_target_cost)
