from google.cloud import bigquery  # https://pypi.org/project/google-cloud-bigquery/
from roas_manager.models import Log
from roas_manager.maintanence import date_range
from annoying.functions import get_object_or_None
from RoasManager.settings import CGP_KEY_PATH, BIGQUERY_SELECT, BIGQUERY_FROM, BIGQUERY_DATE_COLUMN, BIGQUERY_WHERE_1,\
    BIGQUERY_WHERE_2
from datetime import datetime


def gcp_query(query, date, date2=None):
    if date2:
        final_query = f"""
            SELECT {BIGQUERY_SELECT}
            FROM {BIGQUERY_FROM}
            WHERE {BIGQUERY_DATE_COLUMN} >= '{date}' AND {BIGQUERY_DATE_COLUMN} <= '{date2}'
            AND {BIGQUERY_WHERE_1}
            AND {query}
            AND {BIGQUERY_WHERE_2}
            GROUP BY {BIGQUERY_DATE_COLUMN}
            ORDER BY {BIGQUERY_DATE_COLUMN}
            """
    else:
        final_query = f"""
            SELECT {BIGQUERY_SELECT}
            FROM {BIGQUERY_FROM}
            WHERE {BIGQUERY_DATE_COLUMN} = '{date}'
            AND {BIGQUERY_WHERE_1}
            AND {query}
            AND {BIGQUERY_WHERE_2}
            GROUP BY {BIGQUERY_DATE_COLUMN}
            """
    return final_query

def explicit():
    client = bigquery.Client.from_service_account_json(CGP_KEY_PATH)
    return client


def get_gcp_data(client, query, date, date2=None):
    if date2:
        final_query = gcp_query(query, date, date2)
    else:
        final_query = gcp_query(query, date)
    query_job = client.query(
        final_query,
        location="EU",
    )
    results = query_job.result()
    results_list = []
    for row in results:
        results_list.append([row.day_date, row.tr_24h, row.gmv_24h, row.est_charges_24h])
    return results_list


def save_gcp_data(accounts, date, date2=None, campaign_groups=None, overwrite=False):
    client = explicit()
    results_table = {}
    for account in accounts:
        if not campaign_groups:  # jeżeli nie wskazano określonych grup kampanii, sprawdź wszystkie na koncie
            campaign_groups = account.campaigngroup_set.all()
        if campaign_groups.exists():
            for campaign_group in campaign_groups:
                if campaign_group.sql_query:
                    if date2:  # zapytanie dla zakresu dat
                        run_update = False
                        dates_list = date_range(date, date2)
                        for day in dates_list:  # sprawdź czy dla któregoś z dni brakuje danych
                            log = get_object_or_None(Log, campaign_group=campaign_group, date=day)
                            if log is None:
                                run_update = True
                                break
                            elif (log.transactions is None or log.transactions is 0)\
                                    or (log.gmv is None or log.gmv is 0) or overwrite:
                                run_update = True
                                break
                        if run_update:  # pobierz dane tylko, jeśli są braki
                            results = get_gcp_data(client, campaign_group.sql_query, date, date2)
                        else:
                            print(f"{campaign_group.name} | Dane transakcyjne już istniały, pomijam odpytanie GCP")
                            continue
                        if results:
                            for result in results:
                                Log.objects.update_or_create(campaign_group=campaign_group, date=result[0],
                                                             defaults={'transactions': result[1], 'gmv': result[2],
                                                                       'income': result[3]})
                            results_table[campaign_group.name] = results
                        else:
                            print(f"{campaign_group.name} | Brak wyników w GCP (brak danych albo błędna kwerenda")
                    else:  # zapytanie dla pojedynczej daty
                        log, created = Log.objects.get_or_create(
                            campaign_group=campaign_group, date=date,
                            defaults={'campaign_group': campaign_group, 'date': date}
                        )
                        if (log.transactions is None or log.transactions is 0) or (log.gmv is None or log.gmv is 0) \
                                or overwrite:
                            results = get_gcp_data(client, campaign_group.sql_query, date)
                        else:
                            print(f"{campaign_group.name} | Dane transakcyjne już istniały, pomijam odpytanie GCP")
                            continue
                        if results:
                            for result in results:
                                Log.objects.filter(pk=log.id).update(transactions=result[1], gmv=result[2],
                                                                     income=result[3])
                            results_table[campaign_group.name] = results
                        else:
                            print(f"{campaign_group.name} | Brak danych w GCP")
                else:
                    results_table[campaign_group.name] = [['--', 'Brak kwerendy SQL', '--', '--']]
                    print(f"{datetime.now()} | {campaign_group.name} | Brak kwerendy SQL, pomijam")
        campaign_groups = None
        print(f"{datetime.now()} | {account.account_name} | Zakończono pobieranie danych transakcyjnych")
    return results_table
