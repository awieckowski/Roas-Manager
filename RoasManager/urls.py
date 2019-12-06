"""RoasManager URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf.urls import url
from django.views.generic import TemplateView
from roas_manager.views import *
from django.conf import settings


urlpatterns = [
    path('admin/', admin.site.urls, name="api"),
    path('api/', include('roas_manager.urls')),
    path('', DayOverview.as_view(), name="overview"),
    path('strategies/', Strategies.as_view(), name="strategies"),
    path('google-ads-accounts/', ViewAccounts.as_view(), name="accounts"),
    path('google-ads-accounts/add-account/', AddAccount.as_view(), name="add_account"),
    path('edit-account/<int:pk>/', EditAccount.as_view(), name="edit_account"),
    path('google-ads-accounts/add-campaign-group/', AddCampaignGroup.as_view(), name="add_campaign_group"),
    path('campaign-group/<int:pk>/', EditCampaignGroup.as_view(), name="edit_campaign_group"),
    path('strategy/<int:strategy_id>/edit/', StrategyView.as_view(), name="strategy"),
    path('strategy/<int:strategy_id>/', ViewLog.as_view(), name="log"),
    path('strategy/add/', AddStrategy.as_view(), name="add_strategy"),
    path('get-performance/', CampaignGroupsPerformance.as_view(), name="get_report"),
    path('update-strategy-roas/', SetStrategyRoas.as_view(), name="set_strategy_roas"),
    path('update-campaign-roas/', SetCampaignRoas.as_view(), name="set_campaign_roas"),
    path('campaign_group/<int:campaign_group_id>/add-budget/', AddBudget.as_view(), name="add_budget"),
    path('campaign_group/<int:campaign_group_id>/edit-budget/<int:pk>', EditBudget.as_view(), name="edit_budget"),
    path('verify-budgets/', VerifyBudgetView.as_view(), name="verify_budget"),
    path('update-url-suffix/', SetUrlSuffix.as_view(), name="update_suffix"),
    path('settings/', SettingsPage.as_view(), name="settings"),
    path('accounts/', include('django.contrib.auth.urls')),
    path('campaigns/', CampaignsView.as_view(), name="campaigns"),
    path('campaign/<int:pk>', CampaignEditView.as_view(), name="campaign"),
    path('campaigns/add-campaign/', AddCampaignView.as_view(), name="add_campaign"),
    path('error', ErrorView.as_view(), name="error"),
    path('report/campaign-groups/', CampaignGroupsReportView.as_view(), name="custom_cg_report"),
    path('alerts-settings/<int:pk>/', AlertsSettingsView.as_view(), name="alerts_settings"),
    path('alerts/', AlertsView.as_view(), name="alerts"),
]

if settings.DEBUG:
    import debug_toolbar
    urlpatterns = [
        path('__debug__/', include(debug_toolbar.urls)),
    ] + urlpatterns
