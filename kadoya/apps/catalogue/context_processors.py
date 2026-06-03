from django.core.cache import cache
from .services import CatalogueService

def categories(request) -> dict:
    """
    Injecte les catégories actives dans tous les templates.
    Utilise cache Django pour éviter la requête DB à chaque fois.
    """
    cats = cache.get('active_categories')
    if cats is None:
        cats = list(CatalogueService.get_all_active_categories())
        cache.set('active_categories', cats, 300)
    return {'nav_categories': cats}
