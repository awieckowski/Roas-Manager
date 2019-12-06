from django.contrib import admin

# Register your models here.

from roas_manager.models import *

admin.site.register(Account)
admin.site.register(Log)
admin.site.register(Budget)
admin.site.register(Strategy)
admin.site.register(CampaignGroup)
admin.site.register(Campaign)
admin.site.register(CampaignRoasLog)
admin.site.register(Alert)
admin.site.register(GlobalSettings)

