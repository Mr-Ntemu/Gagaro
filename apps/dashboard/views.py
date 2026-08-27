from django.views.generic import ListView, TemplateView, View
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Q

from apps.accounts.mixins import AdminRequiredMixin
from apps.dashboard.models import PromoCode, InternalNotification, ReviewReport
from apps.dashboard.services import (
    AdminService, StockService, OrderAdminService, PromoService, NotificationService
)
from apps.dashboard.forms import (
    PromoCodeForm, StockUpdateForm, OrderValidationForm, WithdrawalProcessForm
)

# ── Overview ──────────────────────────────────────────────────────────────────

class AdminOverviewView(AdminRequiredMixin, TemplateView):
    """GET /kadmin/ — Vue d'ensemble plateforme."""
    template_name = 'dashboard/overview.html'

    def get_context_data(self, **kwargs):
        ctx   = super().get_context_data(**kwargs)
        ctx.update({
            'kpis':         AdminService.get_platform_kpis(),
            'chart_30d':    AdminService.get_revenue_chart(30),
            'notifs':       NotificationService.get_unread(10),
            'low_stock':    StockService.get_low_stock_products()[:5],
            'to_validate':  OrderAdminService.get_orders_to_validate()[:5],
        })
        return ctx


# ── Commandes ─────────────────────────────────────────────────────────────────

class AdminOrderListView(AdminRequiredMixin, ListView):
    """GET /kadmin/commandes/ — Toutes les commandes."""
    template_name       = 'dashboard/orders/list.html'
    paginate_by         = 25
    context_object_name = 'orders'

    def get_queryset(self):
        return OrderAdminService.get_all_orders(
            status    = self.request.GET.get('status'),
            search    = self.request.GET.get('q'),
            date_from = self.request.GET.get('date_from'),
            date_to   = self.request.GET.get('date_to'),
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from apps.orders.models import Order
        ctx['status_choices'] = Order.OrderStatus.choices
        ctx['status_filter']  = self.request.GET.get('status', '')
        ctx['search_query']   = self.request.GET.get('q', '')
        return ctx


class AdminCustomOrderListView(AdminRequiredMixin, ListView):
    """GET /kadmin/commandes/personnalisees/ — Commandes perso à valider."""
    template_name       = 'dashboard/orders/custom_pending.html'
    context_object_name = 'orders'

    def get_queryset(self):
        return OrderAdminService.get_orders_to_validate()


class AdminOrderDetailView(AdminRequiredMixin, View):
    """
    GET  /kadmin/commandes/<pk>/ → Détail commande
    POST /kadmin/commandes/<pk>/valider/ → Valider commande personnalisée
    """
    template_name = 'dashboard/orders/detail.html'

    def get(self, request, pk):
        from apps.orders.models import Order
        order = get_object_or_404(
            Order.objects.prefetch_related(
                'items__product__images',
                'items__customization_session',
                'items__artisan',
                'status_history__changed_by',
                'payment_attempts',
            ), pk=pk
        )
        form = OrderValidationForm() if order.status == 'paid' else None
        return render(request, self.template_name, {
            'order': order, 'form': form
        })

    def post(self, request, pk):
        from apps.orders.models import Order
        order = get_object_or_404(Order, pk=pk)
        form  = OrderValidationForm(request.POST)

        if not form.is_valid():
            return render(request, self.template_name, {
                'order': order, 'form': form
            })

        approved = form.cleaned_data['approved'] == '1'
        note     = form.cleaned_data.get('admin_note', '')

        try:
            OrderAdminService.validate_custom_order(
                order_id   = pk,
                admin_user = request.user,
                approved   = approved,
                note       = note,
            )
            action = "validée et lancée en confection" if approved else "rejetée"
            messages.success(
                request,
                f"Commande {order.reference} {action}."
            )
        except ValueError as e:
            messages.error(request, str(e))

        return redirect('dashboard:order_detail', pk=pk)


# ── Produits & Stock ──────────────────────────────────────────────────────────

class AdminProductListView(AdminRequiredMixin, ListView):
    """GET /kadmin/produits/ — Tous les produits + gestion stock."""
    template_name       = 'dashboard/products/list.html'
    paginate_by         = 30
    context_object_name = 'products'

    def get_queryset(self):
        from apps.catalogue.models import Product
        qs = (
            Product.objects
            .select_related('category', 'artisan')
            .prefetch_related('images')
            .order_by('-created_at')
        )
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from apps.catalogue.models import Product
        ctx['status_choices'] = Product.ProductStatus.choices
        ctx['stock_form']     = StockUpdateForm()
        return ctx


class AdminProductPendingView(AdminRequiredMixin, ListView):
    """GET /kadmin/produits/en-attente/ — Produits DRAFT à valider."""
    template_name       = 'dashboard/products/pending.html'
    context_object_name = 'products'

    def get_queryset(self):
        from apps.catalogue.models import Product
        return (
            Product.objects
            .filter(status='draft')
            .select_related('category', 'artisan__artisan_profile')
            .prefetch_related('images')
            .order_by('created_at')
        )


class AdminValidateProductView(AdminRequiredMixin, View):
    """POST /kadmin/produits/<pk>/valider/"""

    def post(self, request, pk):
        approved = request.POST.get('approved') == '1'
        note     = request.POST.get('admin_note', '')

        product = StockService.validate_product(pk, request.user, approved, note)
        action  = "approuvé et publié" if approved else "rejeté"
        messages.success(request, f'Produit "{product.title}" {action}.')
        return redirect('dashboard:products_pending')


class AdminUpdateStockView(AdminRequiredMixin, View):
    """POST AJAX /kadmin/produits/stock/"""

    def post(self, request):
        form = StockUpdateForm(request.POST)
        if not form.is_valid():
            return JsonResponse({'success': False, 'errors': form.errors}, status=400)

        product = StockService.update_stock(
            product_id   = form.cleaned_data['product_id'],
            new_quantity = form.cleaned_data['new_quantity'],
            admin_user   = request.user,
        )
        return JsonResponse({
            'success':      True,
            'new_quantity': product.stock_quantity,
            'new_status':   product.status,
            'status_label': product.get_status_display(),
        })


# ── Promotions ────────────────────────────────────────────────────────────────

class AdminPromoListView(AdminRequiredMixin, ListView):
    """GET /kadmin/promos/ — Tous les codes promo."""
    template_name       = 'dashboard/promos/list.html'
    context_object_name = 'promos'
    queryset            = PromoCode.objects.order_by('-valid_from')


class AdminPromoCreateView(AdminRequiredMixin, View):
    """GET/POST /kadmin/promos/nouveau/"""
    template_name = 'dashboard/promos/form.html'

    def get(self, request):
        return render(request, self.template_name, {
            'form': PromoCodeForm(), 'action': 'Créer'
        })

    def post(self, request):
        form = PromoCodeForm(request.POST)
        if form.is_valid():
            promo            = form.save(commit=False)
            promo.created_by = request.user
            promo.save()
            form.save_m2m()
            messages.success(
                request, f"Code promo {promo.code} créé avec succès."
            )
            return redirect('dashboard:promo_list')
        return render(request, self.template_name, {
            'form': form, 'action': 'Créer'
        })


class AdminPromoEditView(AdminRequiredMixin, View):
    """GET/POST /kadmin/promos/<pk>/modifier/"""
    template_name = 'dashboard/promos/form.html'

    def get(self, request, pk):
        promo = get_object_or_404(PromoCode, pk=pk)
        return render(request, self.template_name, {
            'form': PromoCodeForm(instance=promo), 'promo': promo, 'action': 'Modifier'
        })

    def post(self, request, pk):
        promo = get_object_or_404(PromoCode, pk=pk)
        form  = PromoCodeForm(request.POST, instance=promo)
        if form.is_valid():
            form.save()
            messages.success(request, f"Code {promo.code} mis à jour.")
            return redirect('dashboard:promo_list')
        return render(request, self.template_name, {
            'form': form, 'promo': promo, 'action': 'Modifier'
        })


class AdminTogglePromoView(AdminRequiredMixin, View):
    """POST AJAX /kadmin/promos/<pk>/toggle/"""

    def post(self, request, pk):
        promo           = get_object_or_404(PromoCode, pk=pk)
        promo.is_active = not promo.is_active
        promo.save(update_fields=['is_active'])
        return JsonResponse({
            'success':    True,
            'is_active':  promo.is_active,
            'label':      'Actif' if promo.is_active else 'Inactif',
        })


# ── Artisans ─────────────────────────────────────────────────────────────────

class AdminArtisanListView(AdminRequiredMixin, ListView):
    """GET /kadmin/artisans/ — Tous les artisans."""
    template_name       = 'dashboard/artisans/list.html'
    paginate_by         = 20
    context_object_name = 'profiles'

    def get_queryset(self):
        from apps.artisan.models import ArtisanProfile
        qs = (
            ArtisanProfile.objects
            .select_related('user')
            .order_by('-created_at')
        )
        verified = self.request.GET.get('verified')
        if verified == '1':
            qs = qs.filter(is_verified=True)
        elif verified == '0':
            qs = qs.filter(is_verified=False)
        return qs


class AdminVerifyArtisanView(AdminRequiredMixin, View):
    """POST AJAX /kadmin/artisans/<pk>/verifier/"""

    def post(self, request, pk):
        from apps.artisan.models import ArtisanProfile
        profile = get_object_or_404(ArtisanProfile, pk=pk)
        profile.is_verified = not profile.is_verified
        profile.verified_at = timezone.now() if profile.is_verified else None
        profile.save(update_fields=['is_verified', 'verified_at'])
        return JsonResponse({
            'success':     True,
            'is_verified': profile.is_verified,
        })


class AdminWithdrawalListView(AdminRequiredMixin, ListView):
    """GET /kadmin/artisans/retraits/ — Demandes de retrait."""
    template_name       = 'dashboard/artisans/withdrawals.html'
    context_object_name = 'withdrawals'

    def get_queryset(self):
        from apps.artisan.models import WithdrawalRequest
        return (
            WithdrawalRequest.objects
            .select_related('artisan__user')
            .filter(status='pending')
            .order_by('created_at')
        )


class AdminProcessWithdrawalView(AdminRequiredMixin, View):
    """POST /kadmin/artisans/retraits/<pk>/traiter/"""

    def post(self, request, pk):
        from apps.artisan.models import WithdrawalRequest
        withdrawal = get_object_or_404(WithdrawalRequest, pk=pk)
        form       = WithdrawalProcessForm(request.POST)

        if not form.is_valid():
            messages.error(request, "Formulaire invalide.")
            return redirect('dashboard:withdrawals')

        action = form.cleaned_data['action']
        note   = form.cleaned_data.get('admin_note', '')

        withdrawal.status     = action
        withdrawal.admin_note = note
        if action == 'processed':
            withdrawal.processed_at = timezone.now()
        withdrawal.save()

        messages.success(
            request,
            f"Retrait de {withdrawal.artisan.shop_name} "
            f"marqué comme '{withdrawal.get_status_display()}'."
        )
        return redirect('dashboard:withdrawals')


# ── Notifications ─────────────────────────────────────────────────────────────

class AdminNotificationListView(AdminRequiredMixin, ListView):
    """GET /kadmin/notifications/ — Toutes les notifications."""
    template_name       = 'dashboard/notifications.html'
    paginate_by         = 30
    context_object_name = 'notifications'
    queryset            = (
        InternalNotification.objects
        .select_related('related_order', 'related_product', 'related_artisan')
        .order_by('-created_at')
    )


class AdminMarkNotifReadView(AdminRequiredMixin, View):
    """POST AJAX /kadmin/notifications/<pk>/lue/"""

    def post(self, request, pk):
        notif = get_object_or_404(InternalNotification, pk=pk)
        notif.mark_as_read(request.user)
        remaining = InternalNotification.objects.filter(is_read=False).count()
        return JsonResponse({'success': True, 'remaining_unread': remaining})


class AdminMarkAllNotifsReadView(AdminRequiredMixin, View):
    """POST AJAX /kadmin/notifications/tout-lire/"""

    def post(self, request):
        count = InternalNotification.objects.filter(is_read=False).update(
            is_read  = True,
            read_by  = request.user,
            read_at  = timezone.now(),
        )
        return JsonResponse({'success': True, 'marked': count})


# ── Utilisateurs ──────────────────────────────────────────────────────────────

class AdminUserListView(AdminRequiredMixin, ListView):
    """GET /kadmin/utilisateurs/ — Tous les utilisateurs."""
    template_name       = 'dashboard/users/list.html'
    paginate_by         = 25
    context_object_name = 'users'

    def get_queryset(self):
        from apps.accounts.models import KadoyaUser
        qs = KadoyaUser.objects.select_related().order_by('-created_at')
        role = self.request.GET.get('role')
        if role:
            qs = qs.filter(role=role)
        search = self.request.GET.get('q')
        if search:
            qs = qs.filter(
                Q(email__icontains=search)
                | Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
                | Q(phone__icontains=search)
            )
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from apps.accounts.models import UserRole
        ctx['role_choices'] = UserRole.choices
        ctx['role_filter']  = self.request.GET.get('role', '')
        ctx['search_query'] = self.request.GET.get('q', '')
        return ctx


class AdminUserDetailView(AdminRequiredMixin, View):
    """GET /kadmin/utilisateurs/<pk>/ — Détail utilisateur."""
    template_name = 'dashboard/users/detail.html'

    def get(self, request, pk):
        from apps.accounts.models import KadoyaUser
        user = get_object_or_404(KadoyaUser, pk=pk)
        ctx = {'target_user': user}
        if user.is_artisan:
            from apps.artisan.models import ArtisanProfile
            ctx['artisan_profile'] = ArtisanProfile.objects.filter(user=user).first()
        from apps.orders.models import Order
        ctx['recent_orders'] = Order.objects.filter(user=user).order_by('-created_at')[:5]
        from apps.reviews.models import Review
        ctx['recent_reviews'] = Review.objects.filter(user=user).select_related('product').order_by('-created_at')[:5]
        return render(request, self.template_name, ctx)


class AdminToggleUserActiveView(AdminRequiredMixin, View):
    """POST AJAX /kadmin/utilisateurs/<pk>/toggle/"""

    def post(self, request, pk):
        from apps.accounts.models import KadoyaUser
        user = get_object_or_404(KadoyaUser, pk=pk)
        user.is_active = not user.is_active
        user.save(update_fields=['is_active'])
        return JsonResponse({
            'success':   True,
            'is_active': user.is_active,
            'label':     'Actif' if user.is_active else 'Inactif',
        })


class AdminChangeUserRoleView(AdminRequiredMixin, View):
    """POST AJAX /kadmin/utilisateurs/<pk>/role/"""

    def post(self, request, pk):
        from apps.accounts.models import KadoyaUser, UserRole
        user = get_object_or_404(KadoyaUser, pk=pk)
        new_role = request.POST.get('role')
        if new_role not in dict(UserRole.choices):
            return JsonResponse({'success': False, 'error': 'Rôle invalide'}, status=400)
        user.role = new_role
        if new_role == UserRole.ADMIN:
            user.is_staff = True
        user.save(update_fields=['role', 'is_staff'])
        return JsonResponse({
            'success': True,
            'new_role': user.get_role_display(),
        })


# ── Catégories ────────────────────────────────────────────────────────────────

class AdminCategoryListView(AdminRequiredMixin, ListView):
    """GET /kadmin/categories/ — Toutes les catégories."""
    template_name       = 'dashboard/categories/list.html'
    context_object_name = 'categories'

    def get_queryset(self):
        from apps.catalogue.models import Category
        return Category.objects.prefetch_related('products').order_by('order', 'name')


class AdminCategoryCreateView(AdminRequiredMixin, View):
    """GET/POST /kadmin/categories/nouveau/"""
    template_name = 'dashboard/categories/form.html'

    def get(self, request):
        from apps.catalogue.models import Category
        from django import forms
        class CategoryForm(forms.ModelForm):
            class Meta:
                model  = Category
                fields = ['name', 'slug', 'type', 'description', 'icon', 'cover_image', 'is_active', 'order']
                widgets = {
                    'name':        forms.TextInput(attrs={'class': 'form-control'}),
                    'slug':        forms.TextInput(attrs={'class': 'form-control'}),
                    'type':        forms.Select(attrs={'class': 'form-select'}),
                    'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
                    'icon':        forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'bi-image'}),
                    'cover_image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
                    'is_active':   forms.CheckboxInput(attrs={'class': 'form-check-input'}),
                    'order':       forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
                }
        return render(request, self.template_name, {
            'form': CategoryForm(), 'action': 'Créer'
        })

    def post(self, request):
        from apps.catalogue.models import Category
        from django import forms
        class CategoryForm(forms.ModelForm):
            class Meta:
                model  = Category
                fields = ['name', 'slug', 'type', 'description', 'icon', 'cover_image', 'is_active', 'order']
                widgets = {
                    'name':        forms.TextInput(attrs={'class': 'form-control'}),
                    'slug':        forms.TextInput(attrs={'class': 'form-control'}),
                    'type':        forms.Select(attrs={'class': 'form-select'}),
                    'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
                    'icon':        forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'bi-image'}),
                    'cover_image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
                    'is_active':   forms.CheckboxInput(attrs={'class': 'form-check-input'}),
                    'order':       forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
                }
        form = CategoryForm(request.POST, request.FILES)
        if form.is_valid():
            cat = form.save()
            messages.success(request, f'Catégorie "{cat.name}" créée.')
            return redirect('dashboard:category_list')
        return render(request, self.template_name, {
            'form': form, 'action': 'Créer'
        })


class AdminCategoryEditView(AdminRequiredMixin, View):
    """GET/POST /kadmin/categories/<pk>/modifier/"""
    template_name = 'dashboard/categories/form.html'

    def get(self, request, pk):
        from apps.catalogue.models import Category
        from django import forms
        cat = get_object_or_404(Category, pk=pk)
        class CategoryForm(forms.ModelForm):
            class Meta:
                model  = Category
                fields = ['name', 'slug', 'type', 'description', 'icon', 'cover_image', 'is_active', 'order']
                widgets = {
                    'name':        forms.TextInput(attrs={'class': 'form-control'}),
                    'slug':        forms.TextInput(attrs={'class': 'form-control'}),
                    'type':        forms.Select(attrs={'class': 'form-select'}),
                    'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
                    'icon':        forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'bi-image'}),
                    'cover_image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
                    'is_active':   forms.CheckboxInput(attrs={'class': 'form-check-input'}),
                    'order':       forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
                }
        return render(request, self.template_name, {
            'form': CategoryForm(instance=cat), 'category': cat, 'action': 'Modifier'
        })

    def post(self, request, pk):
        from apps.catalogue.models import Category
        from django import forms
        cat = get_object_or_404(Category, pk=pk)
        class CategoryForm(forms.ModelForm):
            class Meta:
                model  = Category
                fields = ['name', 'slug', 'type', 'description', 'icon', 'cover_image', 'is_active', 'order']
                widgets = {
                    'name':        forms.TextInput(attrs={'class': 'form-control'}),
                    'slug':        forms.TextInput(attrs={'class': 'form-control'}),
                    'type':        forms.Select(attrs={'class': 'form-select'}),
                    'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
                    'icon':        forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'bi-image'}),
                    'cover_image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
                    'is_active':   forms.CheckboxInput(attrs={'class': 'form-check-input'}),
                    'order':       forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
                }
        form = CategoryForm(request.POST, request.FILES, instance=cat)
        if form.is_valid():
            form.save()
            messages.success(request, f'Catégorie "{cat.name}" mise à jour.')
            return redirect('dashboard:category_list')
        return render(request, self.template_name, {
            'form': form, 'category': cat, 'action': 'Modifier'
        })


class AdminToggleCategoryView(AdminRequiredMixin, View):
    """POST AJAX /kadmin/categories/<pk>/toggle/"""

    def post(self, request, pk):
        from apps.catalogue.models import Category
        cat = get_object_or_404(Category, pk=pk)
        cat.is_active = not cat.is_active
        cat.save(update_fields=['is_active'])
        return JsonResponse({
            'success':   True,
            'is_active': cat.is_active,
            'label':     'Actif' if cat.is_active else 'Inactif',
        })


# ── Paiements ─────────────────────────────────────────────────────────────────

class AdminPaymentListView(AdminRequiredMixin, ListView):
    """GET /kadmin/paiements/ — Historique des paiements."""
    template_name       = 'dashboard/payments/list.html'
    paginate_by         = 25
    context_object_name = 'payments'

    def get_queryset(self):
        from apps.payments.models import PaymentAttempt
        qs = PaymentAttempt.objects.select_related('order', 'user').order_by('-initiated_at')
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        search = self.request.GET.get('q')
        if search:
            qs = qs.filter(
                Q(mb_payment_id__icontains=search)
                | Q(user__email__icontains=search)
                | Q(order__reference__icontains=search)
            )
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from apps.payments.models import PaymentAttempt
        ctx['status_choices'] = PaymentAttempt.AttemptStatus.choices
        ctx['status_filter']  = self.request.GET.get('status', '')
        ctx['search_query']   = self.request.GET.get('q', '')
        return ctx


class AdminPaymentDetailView(AdminRequiredMixin, View):
    """GET /kadmin/paiements/<pk>/ — Détail paiement."""
    template_name = 'dashboard/payments/detail.html'

    def get(self, request, pk):
        from apps.payments.models import PaymentAttempt
        payment = get_object_or_404(
            PaymentAttempt.objects.select_related('order', 'user'),
            pk=pk
        )
        return render(request, self.template_name, {'payment': payment})


# ── Modération avis (placeholder Sprint 8) ───────────────────────────────────

class AdminReviewModerationView(AdminRequiredMixin, ListView):
    """
    GET /kadmin/avis/moderation/
    Modération des avis clients signalés.
    """
    template_name       = 'dashboard/reviews/moderation.html'
    context_object_name = 'reports'
    queryset            = (
        ReviewReport.objects
        .filter(status='pending')
        .select_related('reported_by')
        .order_by('-created_at')
    )
