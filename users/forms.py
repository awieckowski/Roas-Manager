from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import CustomUser, AlertSettings


class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model = CustomUser
        fields = ('username', 'email')


class CustomUserChangeForm(UserChangeForm):
    class Meta:
        model = CustomUser
        fields = ('username', 'email')


class AlertSettingsForm(forms.ModelForm):
    class Meta:
        model = AlertSettings
        exclude = ['user']
        # fields = '__all__'
