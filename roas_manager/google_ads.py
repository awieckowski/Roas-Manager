from datetime import datetime, timedelta
from googleads import adwords
from operator import itemgetter
from roas_manager.tools import event_alert, calculate_target_cost, get_roas_multiplier, calculate_costs_difference
from roas_manager.models import CampaignGroup, Log, CampaignRoasLog, Account
from django.core.exceptions import ObjectDoesNotExist
from googleads.errors import GoogleAdsServerFault, GoogleAdsError
import logging


logger = logging.getLogger(__name__)


def init_adwords_client(account_id):
    adwords_client = adwords.AdWordsClient.LoadFromStorage()
    try:
        adwords_client.SetClientCustomerId(account_id)
    except GoogleAdsError:
        logger.error(f"{account_id} | Błąd API podczas tworzenia klienta dla konta")
    return adwords_client


def get_strategies(account_id, strategy_id=None, client=None):
    if client is None:
        adwords_client = init_adwords_client(account_id)
    else:
        adwords_client = client
    strategies_service = adwords_client.GetService('BiddingStrategyService', version='v201809')
    if strategy_id:
        selector = {
            'fields': ['Id', 'Name', 'Status', 'BiddingScheme'],
            'predicates': [{
                'field': 'Id',
                'operator': 'EQUALS',
                'values': strategy_id
            }],
        }
    else:
        selector = {
            'fields': ['Id', 'Name', 'Status', 'BiddingScheme'],
        }
    strategies = {}
    try:
        page = strategies_service.get(selector)
    except GoogleAdsError:
        logger.error(f"{account_id} | Błąd API podczas pobierania strategii")
        page = {}
    if 'entries' in page:
        for strategy in page['entries']:
            strategies[strategy['name']] = [strategy['id'], strategy['status']]
    return strategies


def get_campaign_groups(account_id, cg_id=None):
    adwords_client = init_adwords_client(account_id)
    campaign_group_service = adwords_client.GetService('CampaignGroupService', version='v201809')
    if cg_id:
        selector = {
            'fields': ['Id', 'Name', 'Status'],
            'predicates': [{
                'field': 'Id',
                'operator': 'EQUALS',
                'values': cg_id
            }],
        }
    else:
        selector = {
            'fields': ['Id', 'Name', 'Status'],
        }
    campaign_groups = {}
    page = campaign_group_service.get(selector)

    if 'entries' in page:
        for campaign_group in page['entries']:
            campaign_groups[campaign_group['name']] = [campaign_group['id'], campaign_group['status']]
    return campaign_groups


def get_roas_campaigns(account_id, campaign_group_id=None, campaign_id=None):
    adwords_client = init_adwords_client(account_id)
    roas_strategies = get_strategies(account_id, client=adwords_client)
    if roas_strategies:
        strategy_ids = [roas_strategies[strategy][0] for strategy in roas_strategies]
    else:
        print(f'{datetime.now()} | {account_id} | Nie znaleziono żadnych strategii ROAS')
        return None
    campaigns_service = adwords_client.GetService('CampaignService', version='v201809')
    selector = {
        'fields': ['Id', 'Name', 'Status', 'CampaignGroupId', 'BiddingStrategyType', 'BiddingStrategyId'],
        'predicates': [{
            'field': 'Status',
            'operator': 'EQUALS',
            'values': 'ENABLED'
        }, {
            'field': 'BiddingStrategyType',
            'operator': 'IN',
            'values': ['TARGET_ROAS', 'MAXIMIZE_CONVERSION_VALUE']
        }, {
            'field': 'BiddingStrategyId',
            'operator': 'NOT_IN',
            'values': strategy_ids  # pobieramy tylko kampanie ROAS nie należące do żadnej strategii
        }],
    }
    if campaign_group_id:
        cg_predicate = {
            'field': 'campaignGroupId',
            'operator': 'EQUALS',
            'values': campaign_group_id
        }
        selector['predicates'].append(cg_predicate)
    if campaign_id:
        cid_predicate = {
            'field': 'Id',
            'operator': 'EQUALS',
            'values': campaign_id
        }
        selector['predicates'].append(cid_predicate)
    campaigns = {}
    page = campaigns_service.get(selector)

    if 'entries' in page:
        for campaign in page['entries']:
            campaigns[campaign['name']] = [campaign['id'],
                                           campaign['biddingStrategyConfiguration']['biddingStrategyType']]
    return campaigns


def sum_by_date(input_list):
    new_list = [[input_list[0][0], input_list[0][1], input_list[0][2]]]
    j = 0
    for i in range(1, len(input_list)):
        if new_list[j][0] == input_list[i][0]:
            new_list[j] = [new_list[j][0], new_list[j][1] + input_list[i][1], new_list[j][2] + input_list[i][2]]
        else:
            new_list.append([input_list[i][0], input_list[i][1], input_list[i][2]])
            j += 1
    return new_list


def get_roas(strategy_ids_list, strategies_service):
    results = {}
    for strategy_id in strategy_ids_list:
        selector = {
            'fields': ['Name', 'BiddingScheme', 'MaximizeConversionValueTargetRoas', 'TargetRoas'],
            'predicates': [{
                'field': 'Id',
                'operator': 'EQUALS',
                'values': strategy_id
            }],
        }
        # googleads.errors.GoogleAdsServerFault: [SelectorError.INVALID_PREDICATE_VALUE @ selector; trigger:'NAZWA']
        try:
            page = strategies_service.get(selector)
            if 'entries' in page:
                for strategy_data in page['entries']:
                    results[strategy_id] = strategy_data['biddingScheme']['targetRoas']
        except GoogleAdsServerFault:
            print(f'{datetime.now()} | {strategy_id} | Błąd API podczas próby pobrania strategii')
            continue
    return results


def campaign_group_report(adwords_client, campaign_groups, date_from, date_to):
    """
    Pobieranie kosztów i klików z Google Ads i zapisywanie ich do loga.
    :param adwords_client: obiekt Google Ads do inicjalizacji API. Musi być wcześniej nastawiony na określone konto.
    :param campaign_groups: lista obiektów campaign groups
    :param date_from: string z datą
    :param date_to: string z datą
    :return:
    """
    result_dict = {}

    for campaign_group in campaign_groups:
        report = {
            'reportName': 'Yesterday CAMPAIGN_PERFORMANCE_REPORT',
            'dateRangeType': 'CUSTOM_DATE',
            # 'dateRangeType': 'YESTERDAY',
            'reportType': 'CAMPAIGN_PERFORMANCE_REPORT',
            'downloadFormat': 'CSV',
            'selector': {
                'dateRange': {
                    'min': date_from,
                    'max': date_to,
                },
                'fields': ['Date', 'Cost', 'Clicks'],
                'predicates': {
                    'field': 'CampaignGroupId',
                    'operator': 'EQUALS',
                    'values': campaign_group.campaign_group_id
                }
            }
        }
        report_downloader = adwords_client.GetReportDownloader(version='v201809')
        response = report_downloader.DownloadReportAsString(
            report, skip_report_header=True, skip_column_header=True,
            skip_report_summary=True, include_zero_impressions=True)

        response = response.split('\n')
        formatted_response = []
        for i in response:
            i = i.split(',')
            formatted_response.append(i)
        del formatted_response[len(formatted_response) - 1]
        for i in formatted_response:
            i[0] = i[0].replace("'", "")
            i[1] = float(i[1]) / 1000000
            i[2] = float(i[2])
        formatted_response.sort(key=itemgetter(0))
        try:
            result_dict[campaign_group.campaign_group_id] = sum_by_date(formatted_response)
        except IndexError:
            logger.warning(f"Brak zwróconych danych przez API podczas próby pobrania kosztów dla "
                  f"grupy kampanii {campaign_group.name}")
            result_dict[campaign_group.campaign_group_id] = [['1900-01-01', 0, 0]]
    return result_dict


def update_roas(strategies, account, client, override_check=False, dry_run=False):
    """
    Podstawowa funkcja do aktualizacji ROAS w strategiach.
    :param client: obiekt Google Ads do inicjalizacji API. Musi być wcześniej nastawiony na określone konto.
    :param strategies: lista obiektów strategy
    :param account: obiekt na bazie modelu Account
    :param override_check: jeżeli false, nie ustawiaj ROAS tam, gdzie był już danego dnia zmieniany
    :param dry_run: nie zmieniaj nic na koncie jeżeli True
    :return: komunikat
    """
    print(f"""\n=======================================================================\n
    Rozpoczynam aktualizację ROAS dla konta {account.account_name}.\n""")
    strategies_service = client.GetService('BiddingStrategyService', version='v201809')
    operation_list = []
    yesterday = (datetime.today() - timedelta(days=1)).date()
    for strategy in strategies:
        campaign_group = CampaignGroup.objects.filter(strategy=strategy).get()
        if not campaign_group.budget_set.filter(date_from__lte=yesterday, date_to__gte=yesterday).exists():
            print(f"Strategia: {strategy.name} | Nadrzędna grupa kampanii nie ma przypisanego budżetu"
                  f" na wczorajszy dzień")
            continue
        try:
            log = Log.objects.filter(campaign_group=campaign_group, date=yesterday).get()
        except ObjectDoesNotExist:
            logger.warning(f"{strategy.name} | Brak loga za wczoraj dla tej strategii do obliczenia nowego tROASu.")
            continue
        if log.roas_after is not None and override_check is False:
            print(f"Strategia: {strategy.name} | Dla tej strategii ROAS był już dziś aktualizowany, pomijam ją.")
            continue
        current_roas = get_roas([strategy.strategy_id], strategies_service)
        if not current_roas:
            logger.warning(f"Aktualizacja ROAS | Nie odnaleziono strategii o ID {strategy.strategy_id} na koncie!")
            continue
        log.roas_before = current_roas[strategy.strategy_id]
        log.save()
        if strategy.make_changes is True:
            print(f"\nStrategia: {strategy.name}")
            target_cost = calculate_target_cost(campaign_group)
            costs_difference = calculate_costs_difference(campaign_group, target_cost)
            roas_multiplier = get_roas_multiplier(costs_difference)
            new_roas = round(float(log.roas_before) + float(log.roas_before) * roas_multiplier, 2)
            log.roas_after = new_roas
            log.save()

            if log.roas_before != new_roas:
                operation = [{
                    'operator': 'SET',
                    'operand': {
                        'id': strategy.strategy_id,
                        'biddingScheme': {
                            'xsi_type': 'TargetRoasBiddingScheme',
                            'targetRoas': new_roas,
                        }
                    }
                }]
                operation_list.append(operation)
                print(f"ROAS {int(log.roas_before * 100)} => {int(new_roas * 100)}.")
            else:
                print(f"ROAS {int(log.roas_before * 100)} bez zmian.")
        else:
            print(f"{strategy.name} | Zarządzanie budżetem wyłączone, pomijam aktualizację tROASu")

    if operation_list:
        if dry_run is False:
            try:
                strategies_service.mutate(operation_list)
                message = f"\ntROAS został pomyślnie zaktualizowany na koncie {account.account_name}.\n" \
                          f"\n=======================================================================\n"
            except (GoogleAdsServerFault, GoogleAdsError):
                message = f'{datetime.now()} | {account.account_name} | Wystąpił błąd API podczas aktualizacji ROAS'
        else:
            message = f"\nAktualizacja na koncie {account.account_name} pominięta (dry run).\n" \
                      f"\n=======================================================================\n"
    else:
        message = f"\nBrak zmian do wprowadzenia na koncie {account.account_name}.\n" \
                  f"\n=======================================================================\n"
    print(message)
    return message


def save_report_results(report):
    for campaign_group in report:
        cg = CampaignGroup.objects.get(campaign_group_id=campaign_group)
        for day_data in report[campaign_group]:
            if day_data[1] is None:
                day_data[1] = 0
            if day_data[2] is None:
                day_data[2] = 0
            Log.objects.update_or_create(campaign_group=cg, date=day_data[0],
                                         defaults={'cost': day_data[1], 'clicks': day_data[2]})


def update_url_suffix(adwords_client, account):
    adwords_client.SetClientCustomerId(account.account_number)
    adgroup_service = adwords_client.GetService('AdGroupService', version='v201809')
    ad_groups_page_size = 1000
    adgr_offset = 0
    results = {}
    selector_ad_group = {
        'fields': ['Id', 'Status', 'CampaignName', 'CampaignStatus', 'AdGroupType', 'Name', 'FinalUrlSuffix'],
        'predicates': [{
            'field': 'FinalUrlSuffix',
            'operator': 'DOES_NOT_CONTAIN',
            'values': '+'
        }, {
            'field': 'AdGroupType',
            'operator': 'IN',
            'values': ['SEARCH_STANDARD', 'SEARCH_DYNAMIC_ADS', 'DISPLAY_STANDARD', 'SHOPPING_PRODUCT_ADS',
                       'SHOPPING_SHOWCASE_ADS', 'SHOPPING_GOAL_OPTIMIZED_ADS']
        }, {
            'field': 'Status',
            'operator': 'NOT_EQUALS',
            'values': 'REMOVED'
        }, {
            'field': 'CampaignStatus',
            'operator': 'EQUALS',
            'values': 'ENABLED'
        }],
        'ordering': [{
            'field': 'Name',
            'sortOrder': 'ASCENDING'
        }],
        'paging': {
            'startIndex': str(adgr_offset),
            'numberResults': str(ad_groups_page_size)
        }
    }

    more_pages_adg = True
    operation_list = []

    while more_pages_adg:
        ad_gr_page = adgroup_service.get(selector_ad_group)
        if ad_gr_page['totalNumEntries'] == 0:
            logger.info(f"{account.account_name} | Uruchomiany skypt uzupełniający sufiksy URL, brak zmian.")
            return None

        for adgroup in ad_gr_page['entries']:
            ad_gr_name_for_suffix = adgroup['name'].replace(' ', '+')
            ad_gr_name_for_suffix = ad_gr_name_for_suffix.replace('	', '')
            ad_gr_name_for_suffix = ad_gr_name_for_suffix.replace('>', '')
            camp_name_for_suffix = adgroup['campaignName'].replace(' ', '+')
            camp_name_for_suffix = camp_name_for_suffix.replace('>', '+')

            if adgroup['finalUrlSuffix'] is None:
                results[adgroup['name']] = adgroup['campaignName']

                operations = [{
                    'operator': 'SET',
                    'operand': {
                        'id': adgroup['id'],
                        'finalUrlSuffix': 'utm_source=google&utm_medium=cpc&utm_campaign=' + camp_name_for_suffix +
                                          '&ev_adgr=' + ad_gr_name_for_suffix
                    }
                }]
                operation_list.append(operations)

            adgr_offset += ad_groups_page_size
            selector_ad_group['paging']['startIndex'] = str(adgr_offset)
            more_pages_adg = adgr_offset < int(ad_gr_page['totalNumEntries'])

    if results:
        try:
            adgroup_service.mutate(operation_list)
            logger.info(f"{account.account_name} | Uzupełniono sufiksy URL, ilość: {len(results)}")
            return results
        except GoogleAdsError:
            logger.error(f"{account.account_name} | Błąd API podczas uzupełniania sufiksów URL")
            results = 0
            return results

    else:
        logger.info(f"{account.account_name} | Uruchomiany skypt uzupełniający sufiksy URL, brak zmian.")
        return None


def get_results_as_table(account, campaign_groups, date_from, date_to):
    all_results = {}
    adwords_client = init_adwords_client(account.account_number)
    result = campaign_group_report(adwords_client, campaign_groups, date_from, date_to)
    # result = {16752384: [['2019-10-01', 44.08, 366.0]]}
    save_report_results(result)
    for campaign_group in result:
        for day_data in result[campaign_group]:
            day_data.append(account.account_name)  # Dodaj nazwę konta na potrzebę tabeli (interfejs)
    for i in result:
        all_results[CampaignGroup.objects.get(campaign_group_id=i).name] = result[i]
    return all_results


def set_roas_at_campaigns(client, campaigns, source_roas, dry_run=False, override_check=False):
    campaign_service = client.GetService('CampaignService', version='v201809')
    yesterday = (datetime.today() - timedelta(days=1)).date()
    operations = []
    results = {}
    for campaign in campaigns:
        if CampaignRoasLog.objects.filter(campaign=campaign, date=yesterday, roas_after__isnull=False).exists() \
                and override_check is False:
            print(f"Aktualizacja ROAS w kampanii | {campaign.name} | Pomijam, ROAS był już aktualizowany")
            continue
        target_roas = float(source_roas) * float(campaign.roas_modifier)
        account = Account.objects.filter(campaign=campaign).get()
        defaults = {'account': account, 'roas_before': source_roas, 'roas_after': target_roas}
        CampaignRoasLog.objects.update_or_create(campaign=campaign, date=yesterday, defaults=defaults)

        #  https://developers.google.com/adwords/api/docs/reference/v201809/CampaignService.BiddingStrategyType.html
        if campaign.type == 'TARGET_ROAS':
            campaign_type = 'TargetRoasBiddingScheme'
        else:
            campaign_type = 'MaximizeConversionValueBiddingScheme'

        operations.append([{
            'operator': 'SET',
            'operand': {
                'id': campaign.campaign_id,
                'biddingStrategyConfiguration': {
                    'biddingScheme': {
                        'xsi_type': campaign_type,
                        'targetRoas': target_roas,
                    }
                }
            }
        }])
        results[campaign.name] = [int(source_roas * 100), int(target_roas * 100)]

    if operations and not dry_run:
        try:
            campaign_service.mutate(operations)
            print(f'Aktualizacja ROAS w kampaniach na koncie zakończona pomyślnie')
        except GoogleAdsError:
            logger.error(f"Błąd API podczas próby aktualizacji ROAS na poziomie kampanii")
    else:
        print(f'Aktualizacja ROAS w kampaniach: brak operacji do wykonania')
    return results


def set_roas_at_campaigns_wrapper(adwords_client, override_check=False, dry_run=False, accounts=None, strategies=None):
    result = {}
    yesterday = (datetime.today() - timedelta(days=1)).date()
    if accounts is None:
        accounts = Account.objects.all()
    for account in accounts:
        if strategies is None:
            strategies = account.strategy_set.filter(make_changes=True)
        campaigns = account.campaign_set.filter(manage_roas=True)
        if strategies.exists() and campaigns.exists():
            try:
                adwords_client.SetClientCustomerId(account.account_number)
            except GoogleAdsError:
                logger.error(f"{account.account_name} | Błąd podczas próby dostępu do konta przez API")
                continue
            for strategy in strategies:
                if not strategy.campaign_set.all().exists():
                    continue
                if not CampaignGroup.objects.filter(strategy=strategy).exists():
                    continue
                campaign_group = CampaignGroup.objects.filter(strategy=strategy).get()
                if campaign_group.log_set.filter(date=yesterday, roas_after__isnull=False).exists():
                    strategy_log = campaign_group.log_set.filter(date=yesterday).get()
                    source_roas = strategy_log.roas_after
                else:
                    service = adwords_client.GetService('BiddingStrategyService', version='v201809')
                    roas_dict = get_roas([strategy.strategy_id], service)
                    source_roas = roas_dict[strategy.strategy_id]
                campaigns = strategy.campaign_set.filter(manage_roas=True)
                if campaigns.exists():
                    try:
                        new_result = set_roas_at_campaigns(adwords_client, campaigns, source_roas, dry_run=dry_run,
                                                           override_check=override_check)
                        result = {**result, **new_result}
                    except GoogleAdsServerFault:
                        logger.error(f"{strategy.name} | Błąd API podczas aktualizacji ROAS dla kampanii")
                        continue
            strategies = None
        else:
            message = f'Konto {account.account_name} nie ma przypisanych żadnych strategii lub kampanii.'
            print(message)
            strategies = None
    return result
