from django.views.generic import TemplateView

class HomeView(TemplateView):
    """Vue pour la page d'accueil avec affichage masonry des produits."""
    template_name = 'home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # On récupère les 12 derniers produits actifs
        from apps.catalogue.services import CatalogueService
        context['products'] = CatalogueService.get_active_products()[:12]
        return context
    
