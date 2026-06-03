from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import KadoyaUser, UserRole

class KadoyaUserCreationForm(UserCreationForm):
    role = forms.ChoiceField(
        choices=[(UserRole.CLIENT, 'Client'), (UserRole.ARTISAN, 'Artisan')],
        widget=forms.HiddenInput(), # Sera rempli par JS via les cards
        initial=UserRole.CLIENT
    )

    class Meta:
        model = KadoyaUser
        fields = ('email', 'first_name', 'last_name', 'phone', 'role')

class KadoyaUserChangeForm(UserChangeForm):
    class Meta:
        model = KadoyaUser
        fields = ('email', 'first_name', 'last_name', 'phone', 'avatar', 'role')
