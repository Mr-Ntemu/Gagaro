from django import forms
from django.forms import inlineformset_factory
from .models import ArtisanProfile
from apps.catalogue.models import Product, Category, ProductImage
from apps.customization.models import FrameOption


class ArtisanProfileForm(forms.ModelForm):
    """Formulaire d'édition du profil atelier."""

    class Meta:
        model  = ArtisanProfile
        fields = [
            'shop_name', 'shop_description', 'shop_banner',
            'city', 'quarter', 'specialties',
            'payout_phone', 'payout_operator',
        ]
        widgets = {
            'shop_name':        forms.TextInput(attrs={'class': 'form-control'}),
            'shop_description': forms.Textarea(attrs={
                                  'class': 'form-control', 'rows': 4
                                }),
            'city':             forms.Select(
                                  choices=[
                                    ('', '— Ville —'),
                                    ('Yaoundé','Yaoundé'), ('Douala','Douala'),
                                    ('Bafoussam','Bafoussam'), ('Bamenda','Bamenda'),('Buea','Buea'),
                                  ],
                                  attrs={'class': 'form-select'}
                                ),
            'quarter':          forms.TextInput(attrs={'class': 'form-control'}),
            'specialties':      forms.TextInput(attrs={
                                  'class': 'form-control',
                                  'placeholder': 'cadres bois, aquarelle, portraits...'
                                }),
            'payout_phone':     forms.TextInput(attrs={
                                  'class': 'form-control',
                                  'placeholder': '+237 6XX XXX XXX'
                                }),
            'payout_operator':  forms.Select(attrs={'class': 'form-select'}),
        }


class ProductCreateForm(forms.ModelForm):
    """
    Formulaire de dépôt d'un nouveau produit par un artisan.
    L'artisan est injecté dans __init__ pour masquer ce champ.
    """

    class Meta:
        model  = Product
        fields = [
            'title', 'description', 'category',
            'base_price', 'discounted_price',
            'is_customizable', 'stock_quantity',
            'dimensions', 'weight_grams', 'tags',
        ]
        widgets = {
            'title':            forms.TextInput(attrs={
                                  'class': 'form-control form-control-lg',
                                  'placeholder': 'Nom du produit'
                                }),
            'description':      forms.Textarea(attrs={
                                  'class': 'form-control', 'rows': 5,
                                  'placeholder': 'Description détaillée...'
                                }),
            'category':         forms.Select(attrs={'class': 'form-select'}),
            'base_price':       forms.NumberInput(attrs={
                                  'class': 'form-control',
                                  'placeholder': 'Prix en FCFA',
                                  'min': 500
                                }),
            'discounted_price': forms.NumberInput(attrs={
                                  'class': 'form-control',
                                  'placeholder': 'Laisser vide si pas de promo'
                                }),
            'is_customizable':  forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'stock_quantity':   forms.NumberInput(attrs={
                                  'class': 'form-control', 'min': 0
                                }),
            'dimensions':       forms.TextInput(attrs={
                                  'class': 'form-control',
                                  'placeholder': 'Ex: 20×30 cm, A4...'
                                }),
            'weight_grams':     forms.NumberInput(attrs={
                                  'class': 'form-control',
                                  'placeholder': 'Poids en grammes'
                                }),
            'tags':             forms.TextInput(attrs={
                                  'class': 'form-control',
                                  'placeholder': 'bois, portrait, vintage...'
                                }),
        }

    def __init__(self, artisan, *args, **kwargs):
        self.artisan = artisan
        super().__init__(*args, **kwargs)
        # Filtrer les catégories actives uniquement
        self.fields['category'].queryset = (
            Category.objects.filter(is_active=True).order_by('name')
        )

    def clean(self):
        cleaned = super().clean()
        base     = cleaned.get('base_price')
        discounted = cleaned.get('discounted_price')
        if base and discounted and discounted >= base:
            raise forms.ValidationError(
                "Le prix promotionnel doit être inférieur au prix de base."
            )
        return cleaned

    def save(self, commit=True):
        """Injecte l'artisan et génère le slug automatiquement."""
        product = super().save(commit=False)
        product.artisan = self.artisan
        product.status  = Product.ProductStatus.DRAFT  # en attente review admin

        # Générer un slug unique
        from django.utils.text import slugify
        base_slug = slugify(product.title)
        slug      = base_slug
        counter   = 1
        while Product.objects.filter(slug=slug).exclude(pk=product.pk).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1
        product.slug = slug

        if commit:
            product.save()
        return product


ProductImageFormSet = inlineformset_factory(
    parent_model = Product,
    model        = ProductImage,
    fields       = ['image', 'alt_text', 'is_cover'],
    extra        = 4,       # 4 slots d'upload vides par défaut
    max_num      = 8,       # max 8 images par produit
    can_delete   = True,
    widgets      = {
        'alt_text': forms.TextInput(attrs={
            'class': 'form-control form-control-sm',
            'placeholder': 'Légende (optionnel)'
        }),
    }
)


class SkipEmptyFrameForm(forms.ModelForm):
    """Form qui se considère vide si pas de label."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.empty_permitted = True

    def has_changed(self):
        return bool(self.data.get('label'))


FrameOptionFormSet = forms.inlineformset_factory(
    parent_model = Product,
    model        = FrameOption,
    form         = SkipEmptyFrameForm,
    fields       = ['label', 'width_cm', 'height_cm',
                     'material', 'extra_price', 'is_available'],
    extra        = 3,
    max_num      = 10,
    can_delete   = True,
)
