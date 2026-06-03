from apps.dashboard.services import PromoService

def promo_banner(request) -> dict:
    """
    Injecte la bannière promo active dans tous les templates.
    Mise en cache 300s pour éviter la requête DB à chaque page.
    """
    from django.core.cache import cache
    banner = cache.get('active_promo_banner')
    if banner is None:
        banner = PromoService.get_active_promo_banner()
        # On ne peut pas facilement cacher un objet Model avec ManyToMany
        # si le cache backend n'est pas configuré pour le pickle.
        # Mais pour un simple affichage, ça passe généralement.
        cache.set('active_promo_banner', banner, 300)
    return {'promo_banner': banner}
