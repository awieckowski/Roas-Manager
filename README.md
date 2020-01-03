# ROAS Manager
## Monitor, control and report your PPC performance on Google Ads

If you use tROAS (Target Return On Ad Spend) portfolio strategies in Google Ads, you probably know that they can be really effective. But there is one major drawback - it is difficult to control their long-term spend. Setting daily budgets on a campaign level cripples strategies' performance, so the only way to do it is by manipulating their target ROAS. Doing this manually is quite difficult however - you never know what the spend is going to be, and you risk lowered performance because of strategies needing to recalibrate. And of course, doing it by hand takes a lot of time.
This is why I built ROAS Manager. Set how much you want to spend per campaign group and in what period, link them to portfolio bid strategies, and done - ROAS Manager will correct tROAS values on a portfolio and/or campaign level on a daily basis to achieve target spend by the end of the period. It will also notify you whenever performance doesn't meet its target, create custom reports in Google Sheets, set final URLs suffixes, and more.

## Main features
 
* Control long term spend of your tROAS portfolio strategies in Google Ads while maintaining their optimal performance.
* Connect your Google Ads data with performance results in BigQuery.
* Monitor results via a variety of views: daily summary, budget overview, custom Google Sheets reports.
* Receive email and in-app notifications whenever costs or ROI are not meeting their target.
* Budget double-checking: whenever a budget is added, another user will be requested to verify the amount.
* Automatically add final URL suffixes at Ad Group level

## Requirements

* AdWords API Developer token
* Google Sheets token for exporting reports to gSheets
* BigQuery access token for importing sales performance results
* Postgres database

## Libraries / frameworks

* Django 2 with REST framework
* [Google Ads API](https://developers.google.com/google-ads/api/docs/start)
* [Google Sheets API](https://developers.google.com/sheets/api)
* [BigQuery API](https://cloud.google.com/bigquery/docs/reference/rest/)
* Bootstrap 4

## Setup

1. For production requirements, run `requirements.txt` (`requirements-debug.txt` for `debug=True`)
1. Add jQuery, Bootstrap, [Bootstrap datepicker](https://bootstrap-datepicker.readthedocs.io/en/latest/) files to `/static/js` and  `/static/js` or uncomment cloudflare links at `templates/__base__.html`
2. Rename `RoasManager/.env.example` to `.env` and fill SECRET_KEY and DB_ variables. 
3. For first migrations, run `python manage.py makemigrations users` and then the standard `python manage.py migrate`
3. Above steps are enough to start the application without any of Google APIs integration (so you won't be able to add anything from your Ads account):
  - to use Google Ads API, place your `.yaml` developer token in the root of your home folder
  - for exporting reports to Google Sheets, fill GOOGLE_SHEET_ID, GOOGLE_SHEET_TOKEN_PATH, GOOGLE_SHEET_CREDENTIALS_PATH variables
  - for BigQuery integration, fill CGP_KEY_PATH, BIGQUERY_SELECT, BIGQUERY_FROM, BIGQUERY_DATE_COLUMN, BIGQUERY_WHERE_1, BIGQUERY_WHERE_2
  - for email notifications, fill email variables 
4. Run the application, add your Google Ads Account/Accounts, campaign groups and budgets (Google Ads developer token required). Add your portfolio strategies and link them with campaign groups. Download their performance data, turn on their ROAS adjustment.
5. Set crontab to run `python manage.py go` once per day (`/roas_manager/management/commands/go.py`).
6. For daily income and ROI results, set crontab to run python manage.py gcp_data (`/roas_manager/management/commands/gcp_data.py`).
7. Unit tests are located at `/users/tests.py`

## Screenshots
### Home page:
![Main page](https://github.com/awieckowski/roas_manager/blob/master/readme/main_page.PNG)

### Portfolio strategy performance view:
![Main page](https://github.com/awieckowski/roas_manager/blob/master/readme/log.PNG)

### Strategies list view:
![Main page](https://github.com/awieckowski/roas_manager/blob/master/readme/strategies_view.PNG)

### Settings:
![Main page](https://github.com/awieckowski/roas_manager/blob/master/readme/settings.PNG)

### Campaigns list view:
![Main page](https://github.com/awieckowski/roas_manager/blob/master/readme/campaigns.PNG)



