from django import forms
from .models import FrameOption, EngravingFont
from .validators import (
    validate_image_extension, 
    validate_image_size, 
    validate_image_dimensions,
    validate_engraving_text
)

class PhotoUploadForm(forms.Form):
    """Étape 1 : Upload de la photo personnalisée."""
    photo = forms.ImageField(
        validators=[
            validate_image_extension,
            validate_image_size,
            validate_image_dimensions,
        ],
        widget=forms.FileInput(attrs={
            'accept': 'image/jpeg,image/png,image/webp',
            'class': 'visually-hidden',   # input caché, zone de drop custom
            'id': 'photo-upload-input',
        }),
        help_text="JPG, PNG ou WEBP. Max 10 Mo. Résolution min. 800×600 px."
    )


class FrameSelectionForm(forms.Form):
    """Étape 2 : Sélection de la taille et matière du cadre."""
    frame_option = forms.ModelChoiceField(
        queryset=FrameOption.objects.none(),   # surchargé dans __init__
        widget=forms.RadioSelect(attrs={'class': 'frame-radio'}),
        empty_label=None,
        error_messages={'required': 'Veuillez sélectionner une taille de cadre.'}
    )

    def __init__(self, product, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['frame_option'].queryset = (
            FrameOption.objects.filter(product=product, is_available=True)
                               .order_by('order', 'width_cm')
        )


class EngravingForm(forms.Form):
    """Étape 3 : Texte gravé (optionnel)."""
    engraving_text = forms.CharField(
        max_length=200,
        required=False,
        validators=[validate_engraving_text],
        widget=forms.TextInput(attrs={
            'placeholder': 'Ex: Pour toi, avec tout mon amour ❤️',
            'class': 'form-control form-control-lg',
            'maxlength': '200',
        })
    )
    engraving_position = forms.ChoiceField(
        choices=[('top','Haut'),('bottom','Bas'),('left','Gauche'),('right','Droite')],
        initial='bottom',
        widget=forms.RadioSelect(attrs={'class': 'position-radio'}),
        required=False,
    )
    font = forms.ModelChoiceField(
        queryset=EngravingFont.objects.filter(is_active=True).order_by('order'),
        widget=forms.RadioSelect(attrs={'class': 'font-radio'}),
        required=False,
        empty_label=None,
    )
