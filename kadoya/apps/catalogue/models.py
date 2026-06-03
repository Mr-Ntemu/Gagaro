from decimal import Decimal
from django.db import models
from django.urls import reverse
from apps.core.models import TimeStampedModel
from .managers import ProductManager

class Category(TimeStampedModel):
    """Catégorie principale de produits Kadoya."""

    class CategoryType(models.TextChoices):
        CADRES    = 'cadres',    'Cadres Photos'
        TABLEAUX  = 'tableaux',  'Tableaux Décoratifs'
        SOUVENIRS = 'souvenirs', 'Souvenirs & Cadeaux'

    name        = models.CharField(max_length=100)
    slug        = models.SlugField(unique=True)
    type        = models.CharField(max_length=20, choices=CategoryType.choices)
    description = models.TextField(blank=True)
    icon        = models.CharField(max_length=50, blank=True,
                                   help_text="Classe icône Bootstrap Icons (ex: bi-image)")
    cover_image = models.ImageField(upload_to='categories/', blank=True, null=True)
    is_active   = models.BooleanField(default=True)
    order       = models.PositiveSmallIntegerField(default=0,
                                                    help_text="Ordre d'affichage")

    class Meta:
        verbose_name        = 'Catégorie'
        verbose_name_plural = 'Catégories'
        ordering            = ['order', 'name']

    def __str__(self) -> str:
        return self.name

    def get_absolute_url(self) -> str:
        return reverse('catalogue:listing') + f"?category={self.slug}"


class Product(TimeStampedModel):
    """Produit artisanal mis en vente sur Kadoya."""

    class ProductStatus(models.TextChoices):
        DRAFT     = 'draft',     'Brouillon'
        ACTIVE    = 'active',    'Actif'
        SOLD_OUT  = 'sold_out',  'Épuisé'
        ARCHIVED  = 'archived',  'Archivé'

    # Identité
    title       = models.CharField(max_length=200)
    slug        = models.SlugField(unique=True, max_length=220)
    description = models.TextField()
    category    = models.ForeignKey(Category, on_delete=models.PROTECT,
                                    related_name='products')
    artisan     = models.ForeignKey(
                    'accounts.KadoyaUser',
                    on_delete=models.CASCADE,
                    related_name='products',
                    limit_choices_to={'role': 'artisan'}
                  )

    # Pricing
    base_price        = models.DecimalField(max_digits=10, decimal_places=2)
    discounted_price  = models.DecimalField(max_digits=10, decimal_places=2,
                                             blank=True, null=True)
    
    # Personnalisation
    is_customizable   = models.BooleanField(default=False,
                        help_text="Le client peut uploader une photo pour personnaliser")

    # Stock & Statut
    stock_quantity = models.PositiveIntegerField(default=1)
    status         = models.CharField(max_length=20,
                                       choices=ProductStatus.choices,
                                       default=ProductStatus.DRAFT)

    # Dimensions (pour cadres)
    dimensions     = models.CharField(max_length=50, blank=True,
                                       help_text="Ex: 20x30 cm, A4, etc.")
    weight_grams   = models.PositiveIntegerField(blank=True, null=True,
                                                  help_text="Poids en grammes")

    # SEO & Meta
    tags           = models.CharField(max_length=500, blank=True,
                                       help_text="Tags séparés par des virgules")
    view_count     = models.PositiveIntegerField(default=0, editable=False)

    objects = ProductManager()

    class Meta:
        verbose_name        = 'Produit'
        verbose_name_plural = 'Produits'
        ordering            = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'category']),
            models.Index(fields=['slug']),
        ]

    def __str__(self) -> str:
        return self.title

    def get_absolute_url(self) -> str:
        return reverse('catalogue:detail', kwargs={'slug': self.slug})
    
    @property
    def effective_price(self) -> Decimal:
        """Retourne discounted_price si défini, sinon base_price."""
        return self.discounted_price if self.discounted_price else self.base_price

    @property
    def discount_percentage(self) -> int | None:
        """Retourne le % de réduction si applicable."""
        if self.discounted_price and self.base_price > 0:
            discount = ((self.base_price - self.discounted_price) / self.base_price) * 100
            return int(discount)
        return None

    @property
    def is_in_stock(self) -> bool:
        return self.stock_quantity > 0 and self.status == self.ProductStatus.ACTIVE
    
    @property
    def cover_image(self) -> 'ProductImage | None':
        """Retourne l'image principale du produit."""
        return self.images.filter(is_cover=True).first() or self.images.first()

    @property
    def tag_list(self) -> list[str]:
        """Retourne les tags sous forme de liste Python."""
        if not self.tags:
            return []
        return [tag.strip() for tag in self.tags.split(',') if tag.strip()]


class ProductImage(TimeStampedModel):
    """Image associée à un produit. Un produit peut avoir plusieurs images."""

    product    = models.ForeignKey(Product, on_delete=models.CASCADE,
                                    related_name='images')
    image      = models.ImageField(upload_to='products/%Y/%m/')
    alt_text   = models.CharField(max_length=200, blank=True)
    is_cover   = models.BooleanField(default=False,
                                      help_text="Image principale affichée dans les listings")
    order      = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name        = 'Image produit'
        verbose_name_plural = 'Images produit'
        ordering            = ['order', 'id']

    def save(self, *args, **kwargs):
        """Si is_cover=True, désactiver is_cover sur les autres images du produit."""
        if self.is_cover:
            ProductImage.objects.filter(product=self.product).update(is_cover=False)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"Image for {self.product.title}"
