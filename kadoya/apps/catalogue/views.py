from django.views.generic import ListView, DetailView, RedirectView
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.urls import reverse
from .services import CatalogueService
from .models import Category
from apps.reviews.models import Review
from apps.reviews.services import ReviewService

class CatalogueListingView(ListView):
    """Vue pour le listing des produits avec filtres et recherche."""
    template_name = 'catalogue/listing.html'
    context_object_name = 'products'
    paginate_by = 20

    def get_queryset(self):
        category_slug = self.request.GET.get('category')
        search_query = self.request.GET.get('q')
        sort_by = self.request.GET.get('sort', '-created_at')
        min_price = self.request.GET.get('min_price')
        max_price = self.request.GET.get('max_price')

        return CatalogueService.get_active_products(
            category_slug=category_slug,
            search_query=search_query,
            sort_by=sort_by,
            min_price=float(min_price) if min_price else None,
            max_price=float(max_price) if max_price else None
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        category_slug = self.request.GET.get('category')
        
        context['categories'] = Category.objects.filter(is_active=True)
        context['current_category'] = Category.objects.filter(slug=category_slug).first() if category_slug else None
        context['search_query'] = self.request.GET.get('q', '')
        context['sort_by'] = self.request.GET.get('sort', '-created_at')
        return context

    def render_to_response(self, context, **response_kwargs):
        """Répondre en JSON si la requête est AJAX."""
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            html = render_to_string(
                'catalogue/partials/_product_grid.html', 
                context, 
                request=self.request
            )
            return JsonResponse({
                'html': html,
                'count': context['paginator'].count
            })
        return super().render_to_response(context, **response_kwargs)


class ProductDetailView(DetailView):
    """Vue pour le détail d'un produit."""
    template_name = 'catalogue/detail.html'
    context_object_name = 'product'

    def get_object(self, queryset=None):
        slug = self.kwargs.get('slug')
        product = CatalogueService.get_product_detail(slug)
        self._track_product_view(self.request, product)
        return product

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        product = self.object
        
        # Stats avis (depuis cache)
        stats = ReviewService.get_product_stats(product)
        dist  = ReviewService.get_rating_distribution(product)

        # 3 premiers avis approuvés (le reste chargé en AJAX)
        first_reviews = (
            Review.objects.for_product(product)
            .with_relations()
            .order_by('-created_at')[:3]
        )

        # Le client connecté peut-il laisser un avis ?
        can_review_data = None
        if self.request.user.is_authenticated:
            can_review_data = ReviewService.can_review(
                self.request.user, product
            )

        ctx.update({
            'related_products':    CatalogueService.get_related_products(product),
            'images':              product.images.all(),
            'review_stats':        stats,
            'rating_distribution': dist,
            'first_reviews':       first_reviews,
            'can_review':          can_review_data,
            'review_ajax_url':     reverse(
                'reviews:review_list_ajax',
                kwargs={'product_slug': product.slug}
            ),
        })
        return ctx

    def _track_product_view(self, request, product):
        """Stocke les derniers produits vus en session pour recommandation (Sprint 9)."""
        viewed = request.session.get('viewed_products', [])
        if product.pk not in viewed:
            viewed.append(product.pk)
            request.session['viewed_products'] = viewed[-20:]
        request.session.modified = True


class CategoryListingView(RedirectView):
    """Redirige vers le listing filtré par catégorie."""
    permanent = False

    def get_redirect_url(self, *args, **kwargs):
        slug = kwargs.get('slug')
        return f"{reverse('catalogue:listing')}?category={slug}"
