from httplib2 import Http
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from oauth2client import file, client, tools
from roas_manager.tools import get_campaign_group_table
from RoasManager.settings import GOOGLE_SHEET_ID, CUSTOM_REPORT_SHEET_ID,\
    GOOGLE_SHEET_TOKEN_PATH, GOOGLE_SHEET_CREDENTIALS_PATH
from roas_manager.models import CampaignGroup
from roas_manager.tools import event_alert, get_logs_report
from datetime import datetime, timedelta


SCOPES = 'https://www.googleapis.com/auth/spreadsheets'


def auth():
    store = file.Storage(GOOGLE_SHEET_TOKEN_PATH)
    creds = store.get()
    if not creds or creds.invalid:
        flow = client.flow_from_clientsecrets(GOOGLE_SHEET_CREDENTIALS_PATH, SCOPES)
        creds = tools.run_flow(flow, store)
    service = build('sheets', 'v4', http=creds.authorize(Http()))
    return service


def create_new_sheets(service, tables, spreadsheet_id):
    request = service.spreadsheets().get(spreadsheetId=spreadsheet_id)
    response = request.execute()
    sheets = response['sheets']
    requests = []
    new_sheets = []
    body = {'requests': requests}
    sheets_list = [sheet['properties']['title'] for sheet in sheets]

    for sheet_name in tables:
        if sheet_name not in sheets_list:
            sheet = [
                {
                    "addSheet": {
                        "properties": {
                            "title": sheet_name,
                            "gridProperties": {
                                "rowCount": 35,
                                "columnCount": 13
                            },
                        }
                    }
                }
            ]
            requests.append(sheet)
            new_sheets.append([tables[sheet_name][1], sheet_name])
            print(f"{datetime.now()} | Google Sheets | Zakładka {sheet_name} dodana do listy do utworzenia")

    if requests:
        request = service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body=body)
        request.execute()
        print(f"{datetime.now()} | Google Sheets | Zakładki utworzone")
    return new_sheets


def get_sheet_ids(service, tabs, spreadsheet_id):
    request = service.spreadsheets().get(spreadsheetId=spreadsheet_id)
    response = request.execute()
    sheets = response['sheets']
    for tab in tabs:
        for sheet in sheets:
            if sheet['properties']['title'] == tab[1]:
                sheet_id = sheet['properties']['sheetId']
                campaign_group = tab[0]
                campaign_group.sheet_id = sheet_id
                campaign_group.save()
                continue


def export_tables(service, tables, spreadsheet_id):
    batch_data = []

    for table_name in tables:
        sheet = {
            "range": table_name + '!A1',
            "majorDimension": 'ROWS',
            "values": tables[table_name][0]
        }
        batch_data.append(sheet)

    batch_update_values_request_body = {
        'value_input_option': 'RAW',
        'data': batch_data
    }
    request = service.spreadsheets().values().batchUpdate(spreadsheetId=spreadsheet_id,
                                                          body=batch_update_values_request_body)
    try:
        request.execute()
    except HttpError:
        message = f'{datetime.now()} | Google Sheets | Błąd API podczas eksportu danych do arkusza'
        event_alert(message=message)


def export_tables_to_sheets(campaign_groups, date):
    data_for_export = {}
    for campaign_group in campaign_groups:
        account_name = campaign_group.account.account_name
        tab_name = f"{account_name}_{campaign_group.name}"
        table = get_campaign_group_table(campaign_group, date, headers=True)
        data_for_export[tab_name] = [table, campaign_group]
    return data_for_export


def export_tables_to_sheets_custom_report(campaign_groups, date_from, date_to):
    data_for_export = {}
    for campaign_group in campaign_groups:
        account_name = campaign_group.account.account_name
        tab_name = f"{account_name}_{campaign_group.name}"
        logs = campaign_group.log_set.all().filter(date__gte=date_from, date__lte=date_to).order_by('date')
        if logs.exists():
            table = get_logs_report(logs, headers=True)
        else:
            return None
        data_for_export[tab_name] = [table, campaign_group]
    return data_for_export


def clear_sheets(service, spreadsheet_id, sheet_ids):
    request = service.spreadsheets().get(spreadsheetId=spreadsheet_id)
    response = request.execute()
    sheet = response['sheets']
    requests = []
    body = {
        "requests": requests
    }
    for i in sheet:
        if str(i['properties']['sheetId']) in sheet_ids:
            clear_sheet_id = [
                {
                    "updateCells": {
                        "range": {
                            "sheetId": i['properties']['sheetId']
                        },
                        "fields": "userEnteredValue"
                    }
                }
            ]
            requests.append(clear_sheet_id)
    if not body['requests']:
        print(f'{datetime.now()} | Google Sheets | Brak arkuszy do wyczyszczenia')
        return None
    try:
        service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body=body).execute()
    except HttpError:
        message = f'{datetime.now()} | Google Sheets | Błąd API podczas próby czyszczenia arkuszy'
        event_alert(message=message)


def assign_sheets(service, campaign_groups, spreadsheet_id):
    assigned_sheets = False
    for campaign_group in campaign_groups:
        if campaign_group.sheet_id is None:
            request = service.spreadsheets().get(spreadsheetId=spreadsheet_id)
            response = request.execute()
            sheet = response['sheets']
            for i in sheet:
                if i['properties']['title'] == f"{campaign_group.account.account_name}_{campaign_group.name}":
                    campaign_group.sheet_id = i['properties']['sheetId']
                    campaign_group.save()
                    assigned_sheets = True
                    print(f"{datetime.now()} | Przypisano istniejący arkusz {i['properties']['sheetId']}"
                          f" do grupy kampanii {campaign_group.name}")
                    continue
    return assigned_sheets


def google_sheets_report(campaign_groups, date_from, date_to):
    google_sheets_service = auth()
    tables_dict = export_tables_to_sheets_custom_report(campaign_groups, date_from, date_to)  # utwórz słownik {zakładka: [tabela, cg]}
    create_new_sheets(google_sheets_service, tables_dict, CUSTOM_REPORT_SHEET_ID)  # utwórz nowe arkusze
    export_tables(google_sheets_service, tables_dict, CUSTOM_REPORT_SHEET_ID)  # zapisz dane w nowych arkuszach
    print(f"{datetime.now()} | Google Sheets | Wyeksportowano rapoty do arkusza {CUSTOM_REPORT_SHEET_ID}")


def update_google_sheets(accounts):
    google_sheets_service = auth()
    yesterday = (datetime.today() - timedelta(days=1)).date()
    campaign_groups = CampaignGroup.objects.all().filter(account__in=accounts).order_by("name")
    tables_dict = export_tables_to_sheets(campaign_groups, yesterday)  # utwórz słownik {zakładka: [tabela, cg]}
    new_sheets = create_new_sheets(google_sheets_service, tables_dict, GOOGLE_SHEET_ID)  # utwórz nowe arkusze
    get_sheet_ids(google_sheets_service, new_sheets, GOOGLE_SHEET_ID)  # zapisz do bazy id nowych arkuszy
    assigned = assign_sheets(google_sheets_service, campaign_groups, GOOGLE_SHEET_ID)  # jeśli nadal są grupy kampanii
    # bez sheetid, to znaczy że istniały wcześniej arkusze od takiej samej nazwie - trzeba przypisać ich id do grupy
    if new_sheets or assigned:
        campaign_groups.all()
    sheet_ids = [campaign_group.sheet_id for campaign_group in campaign_groups]
    clear_sheets(google_sheets_service, GOOGLE_SHEET_ID, sheet_ids)
    export_tables(google_sheets_service, tables_dict, GOOGLE_SHEET_ID)  # zapisz dane w nowych arkuszach
    print(f"{datetime.now()} | Google Sheets | Wyeksportowano rapoty do arkusza {GOOGLE_SHEET_ID}")
