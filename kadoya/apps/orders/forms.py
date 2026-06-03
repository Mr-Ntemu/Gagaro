from django import forms
import re

class CheckoutForm(forms.Form):
    """Formulaire d'informations de livraison."""

    delivery_name    = forms.CharField(
                         max_length=200,
                         label="Nom complet du destinataire",
                         widget=forms.TextInput(attrs={
                             'class': 'form-control form-control-lg',
                             'placeholder': 'Prénom et Nom'
                         })
                       )
    delivery_phone   = forms.CharField(
                         max_length=20,
                         label="Numéro de téléphone",
                         widget=forms.TextInput(attrs={
                             'class': 'form-control',
                             'placeholder': '+237 6XX XXX XXX',
                             'type': 'tel',
                         })
                       )
    delivery_address = forms.CharField(
                         label="Adresse de livraison",
                         widget=forms.Textarea(attrs={
                             'class': 'form-control',
                             'rows': 3,
                             'placeholder': 'Quartier, rue, point de repère...',
                         })
                       )
    delivery_city    = forms.ChoiceField(
                         label="Ville",
                         choices=[
                             ('', '— Sélectionner une ville —'),
                             ('Yaoundé',    'Yaoundé'),
                             ('Douala',     'Douala'),
                             ('Bafoussam',  'Bafoussam'),
                             ('Bamenda',    'Bamenda'),
                             ('Garoua',     'Garoua'),
                             ('Maroua',     'Maroua'),
                             ('Ngaoundéré', 'Ngaoundéré'),
                             ('Bertoua',    'Bertoua'),
                             ('Ebolowa',    'Ebolowa'),
                             ('Limbé',      'Limbé'),
                         ],
                         widget=forms.Select(attrs={'class': 'form-select'})
                       )
    delivery_notes   = forms.CharField(
                         required=False,
                         label="Instructions spéciales (optionnel)",
                         widget=forms.Textarea(attrs={
                             'class': 'form-control',
                             'rows': 2,
                             'placeholder': 'Ex: Sonner au 3ème étage, disponible après 18h...',
                         })
                       )

    def clean_delivery_phone(self) -> str:
        """Valide le format téléphone camerounais."""
        phone = self.cleaned_data['delivery_phone'].strip()
        # Supprimer espaces, tirets, points
        cleaned = re.sub(r'[\s\-\.]', '', phone)
        # Regex simple pour Cameroun (+237 ou 237 suivi de 9 chiffres commençant par 6, 2 ou 3)
        # Mais le prompt dit 6-9
        pattern = r'^(\+237|237)?[6-9]\d{8}$'
        if not re.match(pattern, cleaned):
            raise forms.ValidationError(
                "Numéro invalide. Format attendu : +237 6XX XXX XXX"
            )
        return cleaned
