from django.views.generic import ListView, DetailView, View
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.http import JsonResponse
from django.urls import reverse
from apps.reviews.models import Review, ReviewPhoto
from apps.reviews.forms import ReviewForm
from apps.reviews.services import ReviewService, OrderTrackingService
from apps.accounts.mixins import AdminRequiredMixin, ArtisanRequiredMixin

class OrderHistoryView(LoginRequiredMixin, ListView):
    """
    GET /commandes/historique/
    Historique de toutes les commandes du client connecté.
    """
    template_name       = 'reviews/order_history.html'
    paginate_by         = 10
    context_object_name = 'orders'

    def get_queryset(self):
        from apps.orders.models import Order
        return (
            Order.objects
            .filter(user=self.request.user)
            .prefetch_related(
                'items__product__images',
                'payment_attempts',
            )
            .order_by('-created_at')
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from apps.orders.models import Order
        ctx['status_choices'] = Order.OrderStatus.choices
        ctx['status_filter']  = self.request.GET.get('status', '')
        return ctx


class OrderTrackingView(LoginRequiredMixin, DetailView):
    """
    GET /commandes/suivi/<reference>/
    Suivi temps réel d'une commande avec timeline.
    """
    template_name       = 'reviews/order_tracking.html'
    context_object_name = 'order'

    def get_object(self):
        from apps.orders.models import Order
        return get_object_or_404(
            Order.objects
            .prefetch_related(
                'items__product__images',
                'items__customization_session',
                'status_history',
                'payment_attempts',
                'reviews',
            )
            .select_related('user'),
            reference = self.kwargs['reference'],
            user      = self.request.user,
        )

    def get_context_data(self, **kwargs):
        ctx          = super().get_context_data(**kwargs)
        tracking     = OrderTrackingService.get_tracking_data(self.object)
        ctx.update(tracking)
        return ctx


class ReviewCreateView(LoginRequiredMixin, View):
    """
    GET  /avis/nouveau/<product_slug>/
         → Affiche le formulaire d'avis (si client éligible)

    POST /avis/nouveau/<product_slug>/
         → Crée l'avis + photos et redirige vers la page produit
    """
    template_name = 'reviews/review_form.html'

    def _get_product(self, slug):
        from apps.catalogue.models import Product
        return get_object_or_404(Product, slug=slug, status='active')

    def get(self, request, product_slug):
        product = self._get_product(product_slug)
        check   = ReviewService.can_review(request.user, product)

        if not check['allowed']:
            messages.warning(request, check['reason'])
            return redirect('catalogue:detail', slug=product_slug)

        return render(request, self.template_name, {
            'product': product,
            'form':    ReviewForm(),
            'order':   check['order'],
        })

    def post(self, request, product_slug):
        product = self._get_product(product_slug)
        form    = ReviewForm(request.POST, request.FILES)

        if not form.is_valid():
            return render(request, self.template_name, {
                'product': product, 'form': form
            })

        try:
            ReviewService.create_review(
                user      = request.user,
                product   = product,
                form_data = form.cleaned_data,
                photos    = form.get_photos(),
            )
            messages.success(
                request,
                "Merci pour votre avis ! Il sera visible après modération "
                "par notre équipe (généralement sous 24h)."
            )
            return redirect('catalogue:detail', slug=product_slug)

        except PermissionError as e:
            messages.error(request, str(e))
            return redirect('catalogue:detail', slug=product_slug)

        except ValueError as e:
            form.add_error(None, str(e))
            return render(request, self.template_name, {
                'product': product, 'form': form
            })


class ReviewListAjaxView(View):
    """
    GET AJAX /avis/produit/<product_slug>/
    Retourne les avis approuvés d'un produit en JSON pour chargement dynamique.
    Supporte pagination + filtre par note.
    """

    def get(self, request, product_slug):
        from apps.catalogue.models import Product
        product = get_object_or_404(Product, slug=product_slug)
        try:
            page = int(request.GET.get('page', 1))
        except (TypeError, ValueError):
            page = 1
            
        rating  = request.GET.get('rating')
        per_page = 5

        qs = (
            Review.objects.for_product(product)
            .with_relations()
            .order_by('-created_at')
        )
        if rating:
            try:
                qs = qs.by_rating(int(rating))
            except (TypeError, ValueError):
                pass

        from django.core.paginator import Paginator
        paginator = Paginator(qs, per_page)
        page_obj  = paginator.get_page(page)

        reviews_data = [
            {
                'pk':               r.pk,
                'user_name':        r.user.full_name,
                'rating':           r.rating,
                'title':            r.title,
                'body':             r.body,
                'created_at':       r.created_at.strftime('%d %b %Y'),
                'artisan_reply':    r.artisan_reply,
                'artisan_replied_at': (
                    r.artisan_replied_at.strftime('%d %b %Y')
                    if r.artisan_replied_at else None
                ),
                'photos':           [
                    {
                        'thumb': request.build_absolute_uri(p.thumbnail.url)
                                 if p.thumbnail else None,
                        'full':  request.build_absolute_uri(p.image.url),
                        'caption': p.caption,
                    }
                    for p in r.photos.all()
                ],
            }
            for r in page_obj
        ]

        return JsonResponse({
            'reviews':    reviews_data,
            'has_next':   page_obj.has_next(),
            'has_prev':   page_obj.has_previous(),
            'total':      paginator.count,
            'page':       page,
            'num_pages':  paginator.num_pages,
        })


# ── Vues Admin modération (complète ReviewReport du Sprint 7) ─────────────────

class AdminReviewModerationView(AdminRequiredMixin, ListView):
    """
    GET /kadmin/avis/moderation/
    Liste des avis en attente de modération.
    Remplace le placeholder du Sprint 7.
    """
    template_name       = 'dashboard/reviews/moderation.html'
    paginate_by         = 20
    context_object_name = 'reviews'

    def get_queryset(self):
        return (
            Review.objects
            .filter(status='pending')
            .with_relations()
            .order_by('created_at')
        )


class AdminReviewApproveView(AdminRequiredMixin, View):
    """POST /kadmin/avis/<pk>/approuver/"""

    def post(self, request, pk):
        review = ReviewService.approve_review(pk, request.user)
        messages.success(
            request,
            f"Avis de {review.user.full_name} approuvé et publié."
        )
        return redirect('dashboard:review_moderation')


class AdminReviewRejectView(AdminRequiredMixin, View):
    """POST /kadmin/avis/<pk>/rejeter/"""

    def post(self, request, pk):
        note = request.POST.get('rejection_note', '').strip()
        if not note:
            messages.error(request, "Un motif de rejet est requis.")
            return redirect('dashboard:review_moderation')

        ReviewService.reject_review(pk, request.user, note)
        messages.success(request, "Avis rejeté.")
        return redirect('dashboard:review_moderation')


# ── Réponse artisan ───────────────────────────────────────────────────────────

class ArtisanReplyView(ArtisanRequiredMixin, View):
    """
    POST AJAX /avis/<pk>/repondre/
    Permet à l'artisan de répondre à un avis sur son produit.
    """

    def post(self, request, pk):
        import json
        try:
            data       = json.loads(request.body)
            reply_text = data.get('reply', '').strip()

            if not reply_text:
                return JsonResponse(
                    {'success': False, 'error': 'La réponse ne peut pas être vide.'},
                    status=400
                )

            review = ReviewService.add_artisan_reply(pk, request.user, reply_text)
            return JsonResponse({
                'success':          True,
                'artisan_reply':    review.artisan_reply,
                'artisan_replied_at': review.artisan_replied_at.strftime('%d %b %Y'),
            })

        except PermissionError as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=403)
        except ValueError as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
        except Exception as e:
            return JsonResponse({'success': False, 'error': "Une erreur est survenue."}, status=500)
