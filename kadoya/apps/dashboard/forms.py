from django import forms
from apps.dashboard.models import PromoCode
from decimal import Decimal

class PromoCodeForm(forms.ModelForm):
    """Formulaire création / édition code promo."""

    class Meta:
        model  = PromoCode
        fields = [
            'code', 'occasion', 'description', 'banner_text',
            'discount_type', 'discount_value',
            'min_order_amount', 'max_discount_cap',
            'applicable_categories',
            'max_uses', 'max_uses_per_user',
            'valid_from', 'valid_until', 'is_active',
        ]
        widgets = {
            'code':                forms.TextInput(attrs={
                                     'class': 'form-control text-uppercase',
                                     'placeholder': 'FETE-MERES-2025'
                                   }),
            'occasion':            forms.Select(attrs={'class': 'form-select'}),
            'description':         forms.Textarea(attrs={
                                     'class': 'form-control', 'rows': 3
                                   }),
            'banner_text':         forms.TextInput(attrs={
                                     'class': 'form-control',
                                     'placeholder': '🎁 -20% pour la Fête des mères'
                                   }),
            'discount_type':       forms.Select(attrs={'class': 'form-select'}),
            'discount_value':      forms.NumberInput(attrs={
                                     'class': 'form-control', 'min': 0
                                   }),
            'min_order_amount':    forms.NumberInput(attrs={
                                     'class': 'form-control', 'min': 0
                                   }),
            'max_discount_cap':    forms.NumberInput(attrs={
                                     'class': 'form-control', 'min': 0
                                   }),
            'applicable_categories': forms.CheckboxSelectMultiple(),
            'max_uses':            forms.NumberInput(attrs={
                                     'class': 'form-control', 'min': 1
                                   }),
            'max_uses_per_user':   forms.NumberInput(attrs={
                                     'class': 'form-control', 'min': 1
                                   }),
            'valid_from':          forms.DateTimeInput(
                                     attrs={
                                       'class': 'form-control',
                                       'type': 'datetime-local'
                                     },
                                     format='%Y-%m-%dT%H:%M'
                                   ),
            'valid_until':         forms.DateTimeInput(
                                     attrs={
                                       'class': 'form-control',
                                       'type': 'datetime-local'
                                     },
                                     format='%Y-%m-%dT%H:%M'
                                   ),
            'is_active':           forms.CheckboxInput(
                                     attrs={'class': 'form-check-input'}
                                   ),
        }

    def clean(self):
        cleaned    = super().clean()
        valid_from = cleaned.get('valid_from')
        valid_until = cleaned.get('valid_until')
        if valid_from and valid_until and valid_until <= valid_from:
            raise forms.ValidationError(
                "La date de fin doit être postérieure à la date de début."
            )
        discount_type  = cleaned.get('discount_type')
        discount_value = cleaned.get('discount_value')
        if discount_type == 'percentage' and discount_value and discount_value > 100:
            raise forms.ValidationError(
                "Un pourcentage de réduction ne peut pas dépasser 100%."
            )
        return cleaned


class StockUpdateForm(forms.Form):
    """Formulaire de mise à jour rapide du stock depuis le dashboard."""
    product_id   = forms.IntegerField(widget=forms.HiddenInput)
    new_quantity = forms.IntegerField(
                     min_value = 0,
                     widget    = forms.NumberInput(attrs={
                       'class': 'form-control form-control-sm',
                       'min': 0, 'style': 'width: 80px;'
                     })
                   )


class OrderValidationForm(forms.Form):
    """Formulaire de validation / rejet d'une commande personnalisée."""
    approved    = forms.ChoiceField(
                    choices = [('1', 'Valider et lancer la confection'),
                               ('0', 'Rejeter la commande')],
                    widget  = forms.RadioSelect(
                                attrs={'class': 'form-check-input'}
                              )
                  )
    admin_note  = forms.CharField(
                    required = False,
                    label    = "Note (motif de rejet ou instructions)",
                    widget   = forms.Textarea(attrs={
                      'class': 'form-control', 'rows': 3,
                      'placeholder': 'Optionnel si validation, requis si rejet...'
                    })
                  )

    def clean(self):
        cleaned  = super().clean()
        approved = cleaned.get('approved')
        note     = cleaned.get('admin_note', '').strip()
        if approved == '0' and not note:
            raise forms.ValidationError(
                "Un motif de rejet est obligatoire."
            )
        return cleaned


class WithdrawalProcessForm(forms.Form):
    """Formulaire de traitement d'une demande de retrait."""
    action      = forms.ChoiceField(
                    choices = [
                      ('approved',  'Approuver'),
                      ('processed', 'Marquer comme versée'),
                      ('rejected',  'Rejeter'),
                    ],
                    widget = forms.RadioSelect()
                  )
    admin_note  = forms.CharField(
                    required = False,
                    widget   = forms.Textarea(attrs={
                      'class': 'form-control', 'rows': 2
                    })
                  )
