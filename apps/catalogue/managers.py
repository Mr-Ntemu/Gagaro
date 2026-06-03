from django.db import models
from django.db.models import Q

class ProductQuerySet(models.QuerySet):
    """QuerySet custom pour éviter les requêtes répétitives dans les vues."""

    def active(self):
        """Retourne uniquement les produits actifs et en stock."""
        return self.filter(status='active', stock_quantity__gt=0)

    def by_category(self, category_slug: str):
        """Filtre par slug de catégorie."""
        return self.filter(category__slug=category_slug)

    def search(self, query: str):
        """Recherche dans title, description et tags."""
        return self.filter(
            Q(title__icontains=query) |
            Q(description__icontains=query) |
            Q(tags__icontains=query)
        )

    def with_cover_image(self):
        """Précharge l'image de couverture via prefetch_related optimisé."""
        return self.prefetch_related('images', 'category', 'artisan')

    def price_range(self, min_price: float, max_price: float):
        """Filtre par fourchette de prix."""
        return self.filter(base_price__gte=min_price, base_price__lte=max_price)


class ProductManager(models.Manager):
    def get_queryset(self) -> ProductQuerySet:
        return ProductQuerySet(self.model, using=self._db)

    def active(self) -> ProductQuerySet:
        """Retourne les produits actifs."""
        return self.get_queryset().active()
