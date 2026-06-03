from django.db.models import QuerySet
from django.shortcuts import get_object_or_404
from django.db.models import F
from .models import Product, Category

class CatalogueService:

    @staticmethod
    def get_active_products(
        category_slug: str | None = None,
        search_query: str | None = None,
        sort_by: str = '-created_at',
        min_price: float | None = None,
        max_price: float | None = None,
    ) -> QuerySet:
        """
        Point d'entrée principal pour le listing catalogue.
        Applique tous les filtres et retourne un QuerySet optimisé.
        """
        queryset = Product.objects.active().with_cover_image()

        if category_slug:
            queryset = queryset.by_category(category_slug)

        if search_query:
            queryset = queryset.search(search_query)

        if min_price is not None:
            queryset = queryset.filter(base_price__gte=min_price)
        
        if max_price is not None:
            queryset = queryset.filter(base_price__lte=max_price)

        # Gestion du tri
        sort_mapping = {
            'price_asc': 'base_price',
            'price_desc': '-base_price',
            'newest': '-created_at',
            'popular': '-view_count',
        }
        order_by = sort_mapping.get(sort_by, '-created_at')
        queryset = queryset.order_by(order_by)

        return queryset

    @staticmethod
    def get_product_detail(slug: str) -> Product:
        """
        Retourne un produit actif par slug.
        Incrémente view_count via update().
        """
        # On recupere d'abord pour verifier l'existence et le statut
        product = get_object_or_404(Product.objects.active(), slug=slug)
        
        # Incrementation silencieuse du compteur de vues
        Product.objects.filter(pk=product.pk).update(view_count=F('view_count') + 1)
        
        return product

    @staticmethod
    def get_related_products(product: Product, limit: int = 4) -> QuerySet:
        """
        Retourne des produits actifs de la même catégorie,
        en excluant le produit courant.
        """
        return Product.objects.active() \
            .filter(category=product.category) \
            .exclude(pk=product.pk) \
            .with_cover_image()[:limit]

    @staticmethod
    def get_all_active_categories() -> QuerySet:
        """Retourne les catégories ayant au moins un produit actif."""
        return Category.objects.filter(is_active=True, products__status='active').distinct()
