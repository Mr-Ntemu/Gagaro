from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import TemplateView, ListView, View, DetailView
from django.contrib import messages
from django.http import JsonResponse, Http404
from django.db.models import Q
from .models import ArtisanProfile, WithdrawalRequest
from apps.accounts.mixins import ArtisanRequiredMixin
from apps.catalogue.models import Product
from .services import ArtisanService, FinancialService
from .forms import (
    ArtisanProfileForm, ProductCreateForm, 
    ProductImageFormSet, FrameOptionFormSet
)


class ArtisanDashboardView(ArtisanRequiredMixin, TemplateView):
    """
    GET /artisan/
    Page d'accueil du dashboard artisan.
    KPIs + activité récente + raccourcis.
    """
    template_name = 'artisan/dashboard.html'

    def get_context_data(self, **kwargs):
        ctx   = super().get_context_data(**kwargs)
        user  = self.request.user
        kpis  = ArtisanService.get_dashboard_kpis(user)
        chart = ArtisanService.get_monthly_revenue_chart(user)

        # Dernières ventes (5)
        recent_sales = ArtisanService.get_artisan_sales(user)[:5]

        # Derniers produits (5)
        recent_products = (
            Product.objects.filter(artisan=user)
                           .prefetch_related('images')
                           .order_by('-created_at')[:5]
        )

        ctx.update({
            'kpis':            kpis,
            'chart_data':      chart,
            'recent_sales':    recent_sales,
            'recent_products': recent_products,
        })
        return ctx


class ProductListView(ArtisanRequiredMixin, ListView):
    """
    GET /artisan/produits/
    Liste paginée des produits de l'artisan avec filtres.
    """
    template_name   = 'artisan/product_list.html'
    paginate_by     = 15
    context_object_name = 'products'

    def get_queryset(self):
        qs = (Product.objects
              .filter(artisan=self.request.user)
              .prefetch_related('images', 'frame_options')
              .order_by('-created_at'))

        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)

        search = self.request.GET.get('q')
        if search:
            qs = qs.filter(
                Q(title__icontains=search) | Q(tags__icontains=search)
            )
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['status_filter'] = self.request.GET.get('status', '')
        ctx['search_query']  = self.request.GET.get('q', '')
        ctx['status_choices'] = Product.ProductStatus.choices
        return ctx


class ProductCreateView(ArtisanRequiredMixin, View):
    """
    GET  /artisan/produits/nouveau/  → Affiche le formulaire
    POST /artisan/produits/nouveau/  → Crée le produit + images + options cadre
    """
    template_name = 'artisan/product_create.html'

    def get(self, request):
        form           = ProductCreateForm(artisan=request.user)
        image_formset  = ProductImageFormSet()
        frame_formset  = FrameOptionFormSet()
        return render(request, self.template_name, {
            'form':          form,
            'image_formset': image_formset,
            'frame_formset': frame_formset,
        })

    def post(self, request):
        form          = ProductCreateForm(request.user, request.POST, request.FILES)
        image_formset = ProductImageFormSet(request.POST, request.FILES)
        frame_formset = FrameOptionFormSet(request.POST)

        if form.is_valid() and image_formset.is_valid() and frame_formset.is_valid():
            product = form.save()

            # Sauvegarder les images
            images = image_formset.save(commit=False)
            for img in images:
                img.product = product
                img.save()
            for deleted in image_formset.deleted_objects:
                deleted.delete()

            # Sauvegarder les options de cadre (si produit personnalisable)
            if product.is_customizable:
                frames = frame_formset.save(commit=False)
                for frame in frames:
                    frame.product = product
                    frame.save()
                for deleted in frame_formset.deleted_objects:
                    deleted.delete()

            messages.success(
                request,
                f'Produit "{product.title}" déposé avec succès. '
                f'Il sera visible après validation par notre équipe.'
            )
            return redirect('artisan:product_list')

        return render(request, self.template_name, {
            'form':          form,
            'image_formset': image_formset,
            'frame_formset': frame_formset,
        })


class ProductEditView(ArtisanRequiredMixin, View):
    """
    GET  /artisan/produits/<slug>/modifier/  → Formulaire pré-rempli
    POST /artisan/produits/<slug>/modifier/  → Sauvegarde les modifications

    Un artisan ne peut éditer que SES propres produits.
    """
    template_name = 'artisan/product_edit.html'

    def _get_product(self, request, slug):
        return get_object_or_404(
            Product, slug=slug, artisan=request.user
        )

    def get(self, request, slug):
        product        = self._get_product(request, slug)
        form           = ProductCreateForm(
                           artisan=request.user, instance=product
                         )
        image_formset  = ProductImageFormSet(instance=product)
        frame_formset  = FrameOptionFormSet(instance=product)
        return render(request, self.template_name, {
            'product':       product,
            'form':          form,
            'image_formset': image_formset,
            'frame_formset': frame_formset,
        })

    def post(self, request, slug):
        product       = self._get_product(request, slug)
        form          = ProductCreateForm(
                          request.user, request.POST, request.FILES,
                          instance=product
                        )
        image_formset = ProductImageFormSet(
                          request.POST, request.FILES, instance=product
                        )
        frame_formset = FrameOptionFormSet(request.POST, instance=product)

        if form.is_valid() and image_formset.is_valid() and frame_formset.is_valid():
            updated = form.save()

            images = image_formset.save(commit=False)
            for img in images:
                img.product = updated
                img.save()
            for deleted in image_formset.deleted_objects:
                deleted.delete()

            frames = frame_formset.save(commit=False)
            for frame in frames:
                frame.product = updated
                frame.save()
            for deleted in frame_formset.deleted_objects:
                deleted.delete()

            messages.success(request, f'Produit "{updated.title}" mis à jour.')
            return redirect('artisan:product_list')

        return render(request, self.template_name, {
            'product':       product,
            'form':          form,
            'image_formset': image_formset,
            'frame_formset': frame_formset,
        })


class ToggleProductStatusView(ArtisanRequiredMixin, View):
    """
    POST AJAX /artisan/produits/<slug>/toggle/
    Active ou désactive un produit (draft ↔ active).
    Un produit SOLD_OUT ou ARCHIVED ne peut pas être toggleé via cette vue.
    """

    def post(self, request, slug):
        product = get_object_or_404(Product, slug=slug, artisan=request.user)

        if product.status not in ['draft', 'active']:
            return JsonResponse({
                'success': False,
                'error':   'Ce produit ne peut pas être activé/désactivé.'
            }, status=400)

        product.status = 'active' if product.status == 'draft' else 'draft'
        product.save(update_fields=['status', 'updated_at'])

        return JsonResponse({
            'success':    True,
            'new_status': product.status,
            'label':      product.get_status_display(),
        })


class ProductDeleteView(ArtisanRequiredMixin, View):
    """
    POST /artisan/produits/<slug>/supprimer/
    Suppression logique (archive) uniquement si aucune commande active.
    """

    def post(self, request, slug):
        product = get_object_or_404(Product, slug=slug, artisan=request.user)

        # Vérifier qu'il n'y a pas de commandes actives sur ce produit
        has_active_orders = product.orderitem_set.filter(
            order__status__in=['paid', 'confirmed', 'in_craft', 'shipped']
        ).exists()

        if has_active_orders:
            messages.error(
                request,
                "Impossible de supprimer ce produit : "
                "des commandes sont en cours de traitement."
            )
            return redirect('artisan:product_list')

        product.status = Product.ProductStatus.ARCHIVED
        product.save(update_fields=['status', 'updated_at'])

        messages.success(request, f'"{product.title}" archivé avec succès.')
        return redirect('artisan:product_list')


class SalesView(ArtisanRequiredMixin, ListView):
    """
    GET /artisan/ventes/
    Liste paginée des ventes avec filtres par statut et période.
    """
    template_name       = 'artisan/sales.html'
    paginate_by         = 20
    context_object_name = 'sales'

    def get_queryset(self):
        status    = self.request.GET.get('status')
        date_from = self.request.GET.get('date_from')
        date_to   = self.request.GET.get('date_to')

        return ArtisanService.get_artisan_sales(
            artisan_user = self.request.user,
            status_filter = status,
            date_from   = date_from,
            date_to     = date_to,
        )

    def get_context_data(self, **kwargs):
        ctx  = super().get_context_data(**kwargs)
        from apps.orders.models import Order
        ctx['status_choices'] = Order.OrderStatus.choices
        ctx['status_filter']  = self.request.GET.get('status', '')
        ctx['date_from']      = self.request.GET.get('date_from', '')
        ctx['date_to']        = self.request.GET.get('date_to', '')
        return ctx


class FinancialView(ArtisanRequiredMixin, TemplateView):
    """
    GET /artisan/finances/
    Tableau de bord financier : revenus, commissions, retraits.
    """
    template_name = 'artisan/financial.html'

    def get_context_data(self, **kwargs):
        ctx     = super().get_context_data(**kwargs)
        user    = self.request.user
        profile = get_object_or_404(ArtisanProfile, user=user)

        ctx.update({
            'profile':   profile,
            'summary':   FinancialService.get_financial_summary(profile),
            'chart':     ArtisanService.get_monthly_revenue_chart(user),
            'withdrawals': profile.withdrawal_requests.order_by('-created_at')[:10],
        })
        return ctx


class ArtisanProfileEditView(ArtisanRequiredMixin, View):
    """
    GET  /artisan/profil/  → Formulaire profil atelier
    POST /artisan/profil/  → Sauvegarde les modifications
    """
    template_name = 'artisan/profile_edit.html'

    def _get_profile(self, user):
        profile, _ = ArtisanProfile.objects.get_or_create(
            user=user,
            defaults={'shop_name': f"Atelier de {user.full_name}"}
        )
        return profile

    def get(self, request):
        profile = self._get_profile(request.user)
        form    = ArtisanProfileForm(instance=profile)
        return render(request, self.template_name, {
            'profile': profile, 'form': form
        })

    def post(self, request):
        profile = self._get_profile(request.user)
        form    = ArtisanProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Profil mis à jour avec succès.")
            return redirect('artisan:dashboard')
        return render(request, self.template_name, {
            'profile': profile, 'form': form
        })


class ArtisanOrderDetailView(ArtisanRequiredMixin, DetailView):
    """
    GET /artisan/commandes/<reference>/
    Détail d'une commande concernant l'artisan (items lui appartenant uniquement).
    """
    template_name       = 'artisan/order_detail.html'
    context_object_name = 'order'

    def get_object(self):
        from apps.orders.models import Order
        order = get_object_or_404(Order, reference=self.kwargs['reference'])

        # Vérifier que cette commande a au moins un item appartenant à cet artisan
        has_items = order.items.filter(artisan=self.request.user).exists()
        if not has_items:
            raise Http404("Commande non trouvée.")
        return order

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # Filtrer uniquement les items de cet artisan
        ctx['my_items'] = self.object.items.filter(artisan=self.request.user)
        return ctx
