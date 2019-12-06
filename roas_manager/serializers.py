from rest_framework import serializers
from .models import Strategy, CampaignGroup, Account, Campaign, Budget
from users.models import CustomUser


class StrategySerializer(serializers.HyperlinkedModelSerializer):
    accounts = Account.objects.all()
    account = serializers.PrimaryKeyRelatedField(queryset=accounts, many=False)
    users = CustomUser.objects.all()
    user = serializers.PrimaryKeyRelatedField(queryset=users, many=True)

    class Meta:
        model = Strategy
        fields = ('id', 'name', 'account', 'make_changes', 'strategy_id', 'user')


class CampaignGroupSerializer(serializers.HyperlinkedModelSerializer):
    accounts = Account.objects.all()
    account = serializers.PrimaryKeyRelatedField(queryset=accounts, many=False)
    users = CustomUser.objects.all()
    user = serializers.PrimaryKeyRelatedField(queryset=users, many=True)

    class Meta:
        model = CampaignGroup
        fields = ('name', 'campaign_group_id', 'account', 'user')


class CampaignSerializer(serializers.HyperlinkedModelSerializer):
    accounts = Account.objects.all()
    account = serializers.PrimaryKeyRelatedField(queryset=accounts, many=False)
    users = CustomUser.objects.all()
    user = serializers.PrimaryKeyRelatedField(queryset=users, many=True)

    class Meta:
        model = Campaign
        fields = ('name', 'type', 'campaign_id', 'manage_roas', 'account', 'user')


class BudgetSerializer(serializers.HyperlinkedModelSerializer):

    class Meta:
        model = Budget
        fields = ('id', 'verified')
