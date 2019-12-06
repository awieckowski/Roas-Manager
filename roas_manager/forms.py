from django import forms
from .models import *


class BaseForm(forms.Form):
    def __init__(self, *args, **kwargs):
        super(BaseForm, self).__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'


class BudgetForm(BaseForm):
    to_spend = forms.DecimalField(label='Kwota budżetu', decimal_places=2)
    date_from = forms.DateField(label='Początek')
    date_to = forms.DateField(label='Koniec')


class GetCostClicksForm(forms.Form):
    accounts = Account.objects.all()
    campaign_groups = CampaignGroup.objects.all()
    account = forms.ModelChoiceField(label='Konto', queryset=accounts)
    campaign_group = forms.ModelMultipleChoiceField(queryset=campaign_groups,
                                                    widget=forms.CheckboxSelectMultiple(attrs={'checked': 'checked'}),
                                                    label="Grupy kampanii do aktualizacji")
    date_from = forms.DateField(label='Pobierz dane od dnia:')
    date_to = forms.DateField(label='do dnia:')


class AccountForm(BaseForm):
    campaign_group_id = forms.CharField(disabled=True)
    account_name = forms.CharField(label='Nazwa konta')
    account_name.widget.attrs['size'] = '50'
    account_number = forms.CharField(label='Numer konta')
    users = CustomUser.objects.all()
    user = forms.ModelMultipleChoiceField(label='Właściciel', queryset=users, widget=forms.CheckboxSelectMultiple)


class CampaignGroupForm(forms.ModelForm):
    class Meta:
        model = CampaignGroup
        fields = '__all__'
    campaign_group_id = forms.CharField(disabled=True)


class SetRoasForm(forms.Form):
    accounts = Account.objects.all()
    account = forms.ModelChoiceField(label='Konto', queryset=accounts)
    account.widget.attrs['class'] = 'form-control'
    campaign_groups = CampaignGroup.objects.all()
    campaign_group = forms.ModelMultipleChoiceField(queryset=campaign_groups,
                                                    widget=forms.CheckboxSelectMultiple(),
                                                    label="Nadrzędne grupy kampanii:")
    campaign_group.widget.attrs['class'] = "form-check-input"
    strategies = Strategy.objects.all()
    strategy = forms.ModelMultipleChoiceField(queryset=strategies, widget=forms.CheckboxSelectMultiple(),
                                              label="Strategie źródłowe:")
    strategy.widget.attrs['class'] = "form-check-input"
    override_check = forms.BooleanField(label="Pomiń elementy, których tROAS był już dziś aktualizowany")
    override_check.initial = True
    override_check.required = False


class StrategyForm(forms.Form):
    name = forms.CharField(label='Nazwa strategii:')
    name.widget.attrs['class'] = 'form-control'
    name.widget.attrs['size'] = '50'
    accounts = Account.objects.all()
    account = forms.ModelChoiceField(label='Konto:', queryset=accounts)
    account.widget.attrs['class'] = 'form-control'
    # account.disabled = True
    campaign_groups = CampaignGroup.objects.all()
    campaign_group = forms.ModelChoiceField(label='Grupa kampanii:', queryset=campaign_groups)
    campaign_group.widget.attrs['class'] = 'form-control'
    make_changes = forms.BooleanField(label='Zarządzanie budżetem:')
    make_changes.widget.attrs['class'] = "custom-control-input"
    make_changes.required = False
    strategy_id = forms.IntegerField(label='Nr ID strategii:')
    strategy_id.widget.attrs['class'] = 'form-control'
    strategy_id.disabled = True


class GlobalSettingsForm(BaseForm):
    tax = forms.DecimalField(label='Podatek (mnożnik):', decimal_places=2)
    return_rate = forms.DecimalField(label='Wysokość zwrotów (mnożnik):', decimal_places=2)


class CampaignForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super(CampaignForm, self).__init__(*args, **kwargs)
        self.fields['type'].disabled = True
        self.fields['campaign_id'].disabled = True

    class Meta:
        model = Campaign
        fields = '__all__'
