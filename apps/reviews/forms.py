from django import forms
from apps.reviews.models import Review
from apps.reviews.validators import (
    validate_review_photo_extension,
    validate_review_photo_size,
    validate_review_body
)

class ReviewForm(forms.ModelForm):
    """
    Formulaire de soumission d'un avis client.
    Les photos sont gérées séparément via des champs FileField multiples.
    """

    # Champs photos (jusqu'à 3)
    photo_1 = forms.ImageField(
                required   = False,
                validators = [
                    validate_review_photo_extension,
                    validate_review_photo_size,
                ],
                widget = forms.FileInput(attrs={
                    'accept': 'image/jpeg,image/png,image/webp',
                    'class': 'review-photo-input visually-hidden',
                    'id': 'photo-1',
                })
              )
    photo_2 = forms.ImageField(
                required=False,
                validators=[
                    validate_review_photo_extension,
                    validate_review_photo_size,
                ],
                widget=forms.FileInput(attrs={
                    'accept': 'image/jpeg,image/png,image/webp',
                    'class': 'review-photo-input visually-hidden',
                    'id': 'photo-2',
                })
              )
    photo_3 = forms.ImageField(
                required=False,
                validators=[
                    validate_review_photo_extension,
                    validate_review_photo_size,
                ],
                widget=forms.FileInput(attrs={
                    'accept': 'image/jpeg,image/png,image/webp',
                    'class': 'review-photo-input visually-hidden',
                    'id': 'photo-3',
                })
              )

    class Meta:
        model  = Review
        fields = ['rating', 'title', 'body']
        widgets = {
            'rating': forms.RadioSelect(
                        attrs={'class': 'star-radio visually-hidden'}
                      ),
            'title':  forms.TextInput(attrs={
                        'class': 'form-control',
                        'placeholder': 'Résumez votre expérience (optionnel)'
                      }),
            'body':   forms.Textarea(attrs={
                        'class': 'form-control',
                        'rows': 5,
                        'placeholder': (
                            'Décrivez votre expérience avec ce produit : '
                            'qualité, délai de livraison, conformité...'
                        ),
                        'minlength': '10',
                      }),
        }

    def clean_body(self):
        body = self.cleaned_data.get('body', '')
        validate_review_body(body)
        return body

    def clean_rating(self):
        rating = self.cleaned_data.get('rating')
        try:
            rating = int(rating)
        except (TypeError, ValueError):
            raise forms.ValidationError("La note doit être un nombre.")
            
        if rating not in range(1, 6):
            raise forms.ValidationError("La note doit être entre 1 et 5.")
        return rating

    def get_photos(self) -> list:
        """Retourne les fichiers photos uploadés (non vides)."""
        return [
            self.cleaned_data[f'photo_{i}']
            for i in range(1, 4)
            if self.cleaned_data.get(f'photo_{i}')
        ]
