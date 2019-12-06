from django.urls import include, path
from rest_framework import routers
from . import views

router = routers.DefaultRouter()
router.register(r'strategies', views.StrategyViewSet)
router.register(r'campaign-groups', views.CampaignGroupViewSet)
router.register(r'campaigns', views.CampaignViewSet)
router.register(r'budgets', views.BudgetViewSet)


urlpatterns = [
    path('', include(router.urls)),
    path('api-auth/', include('rest_framework.urls', namespace='rest_framework')),
]