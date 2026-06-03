from django.http import JsonResponse
from django.views import View
from django.urls import reverse
from django.shortcuts import get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin

from .services import RecommendationService, AnonymousRecommendationService

class RecommendationAPIView(LoginRequiredMixin, View):
    """
    GET AJAX /api/reco/
    Retourne les recommandations personnalisées en JSON.
    """

    def get(self, request):
        context     = request.GET.get('context', 'global')
        limit       = min(int(request.GET.get('limit', 8)), 12)
        exclude_ids = [
            int(x) for x in request.GET.get('exclude', '').split(',')
            if x.strip().isdigit()
        ]
        cat_ids = [
            int(x) for x in request.GET.get('categories', '').split(',')
            if x.strip().isdigit()
        ]

        products = RecommendationService.get_recommendations(
            user                = request.user,
            context             = context,
            limit               = limit,
            exclude_product_ids = exclude_ids or None,
            category_ids        = cat_ids or None,
        )

        data = [
            {
                'pk':           p.pk,
                'title':        p.title,
                'slug':         p.slug,
                'price':        str(p.effective_price),
                'has_discount': bool(p.discounted_price),
                'discount_pct': p.discount_percentage,
                'category':     p.category.name,
                'cover_url':    (
                    request.build_absolute_uri(p.cover_image.image.url)
                    if p.cover_image else None
                ),
                'detail_url':   reverse('catalogue:detail',
                                        kwargs={'slug': p.slug}),
                'is_customizable': p.is_customizable,
            }
            for p in products
        ]

        return JsonResponse({'products': data, 'count': len(data)})


class AnonymousRecommendationAPIView(View):
    """
    GET AJAX /api/reco/anonyme/
    Recommandations pour les utilisateurs non connectés.
    """

    def get(self, request):
        limit       = min(int(request.GET.get('limit', 8)), 12)
        exclude_ids = [
            int(x) for x in request.GET.get('exclude', '').split(',')
            if x.strip().isdigit()
        ]

        products = AnonymousRecommendationService.get_recommendations(
            request             = request,
            limit               = limit,
            exclude_product_ids = exclude_ids or None,
        )

        data = [
            {
                'pk':        p.pk,
                'title':     p.title,
                'slug':      p.slug,
                'price':     str(p.effective_price),
                'category':  p.category.name,
                'cover_url': (
                    request.build_absolute_uri(p.cover_image.image.url)
                    if p.cover_image else None
                ),
                'detail_url': reverse('catalogue:detail',
                                      kwargs={'slug': p.slug}),
            }
            for p in products
        ]
        return JsonResponse({'products': data, 'count': len(data)})


class TrackBehaviorView(LoginRequiredMixin, View):
    """
    POST AJAX /api/reco/track/
    Endpoint de tracking comportemental côté client.
    """

    ALLOWED_EVENT_TYPES = {'view', 'cart', 'customize'}

    def post(self, request):
        import json
        try:
            data       = json.loads(request.body)
            product_id = data.get('product_id')
            event_type = data.get('event_type')

            if event_type not in self.ALLOWED_EVENT_TYPES:
                return JsonResponse(
                    {'success': False, 'error': 'event_type invalide'},
                    status=400
                )

            from apps.catalogue.models import Product
            product = get_object_or_404(Product, pk=product_id, status='active')

            RecommendationService.track_event(
                user       = request.user,
                product    = product,
                event_type = event_type,
            )
            return JsonResponse({'success': True})

        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
