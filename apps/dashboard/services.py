from decimal import Decimal
from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import timedelta
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from apps.dashboard.models import PromoCode, InternalNotification

class AdminService:

    @staticmethod
    def get_platform_kpis() -> dict:
        """
        KPIs globaux de la plateforme Kadoya.
        Une seule passe d'agrégation pour la performance.
        """
        from apps.orders.models import Order
        from apps.catalogue.models import Product
        from apps.accounts.models import KadoyaUser
        from apps.artisan.models import WithdrawalRequest, ArtisanProfile

        now       = timezone.now()
        today     = now.date()
        week_ago  = now - timedelta(days=7)
        month_ago = now - timedelta(days=30)

        orders_agg = Order.objects.aggregate(
            today       = Count('pk', filter=Q(created_at__date=today)),
            pend_pay    = Count('pk', filter=Q(status='pending')),
            to_validate = Count('pk', filter=Q(status='paid')),
            in_craft    = Count('pk', filter=Q(status='in_craft')),
            rev_today   = Sum('total_amount',
                              filter=Q(paid_at__date=today)),
            rev_month   = Sum('total_amount',
                              filter=Q(paid_at__gte=month_ago)),
            rev_total   = Sum('total_amount',
                              filter=Q(status__in=[
                                'paid','confirmed','in_craft',
                                'shipped','delivered'
                              ])),
        )

        return {
            'orders_today':       orders_agg['today']       or 0,
            'orders_pending_pay': orders_agg['pend_pay']    or 0,
            'orders_to_validate': orders_agg['to_validate'] or 0,
            'orders_in_craft':    orders_agg['in_craft']    or 0,
            'revenue_today':      orders_agg['rev_today']   or Decimal('0'),
            'revenue_month':      orders_agg['rev_month']   or Decimal('0'),
            'revenue_total':      orders_agg['rev_total']   or Decimal('0'),
            'new_clients_week':   KadoyaUser.objects.clients()
                                    .filter(created_at__gte=week_ago).count(),
            'new_artisans_week':  KadoyaUser.objects.artisans()
                                    .filter(created_at__gte=week_ago).count(),
            'products_pending':   Product.objects.filter(status='draft').count(),
            'stock_alerts':       Product.objects.filter(
                                    status='active',
                                    stock_quantity__lte=3
                                  ).count(),
            'withdrawal_pending': WithdrawalRequest.objects.filter(
                                    status='pending'
                                  ).count(),
            'notifs_unread':      InternalNotification.objects.filter(
                                    is_read=False
                                  ).count(),
        }

    @staticmethod
    def get_revenue_chart(days: int = 30) -> list[dict]:
        """
        Données pour le graphique des revenus des N derniers jours.
        Retourne une liste de dicts pour Chart.js :
        [{'date': '2024-12-01', 'revenue': 145000, 'orders': 5}, ...]
        """
        from apps.orders.models import Order
        from django.db.models.functions import TruncDate

        since = timezone.now() - timedelta(days=days)

        data = (
            Order.objects
            .filter(paid_at__gte=since,
                    status__in=['paid','confirmed','in_craft','shipped','delivered'])
            .annotate(day=TruncDate('paid_at'))
            .values('day')
            .annotate(
                revenue = Sum('total_amount'),
                orders  = Count('pk'),
            )
            .order_by('day')
        )

        return [
            {
                'date':    item['day'].strftime('%d/%m'),
                'revenue': float(item['revenue'] or 0),
                'orders':  item['orders'],
            }
            for item in data
        ]


class StockService:

    STOCK_LOW_THRESHOLD = 3  # Alerte si stock <= 3

    @staticmethod
    def get_low_stock_products():
        """Produits actifs avec stock bas ou épuisés."""
        from apps.catalogue.models import Product
        return (
            Product.objects
            .filter(
                status__in=['active', 'sold_out'],
                stock_quantity__lte=StockService.STOCK_LOW_THRESHOLD
            )
            .select_related('category', 'artisan')
            .order_by('stock_quantity')
        )

    @staticmethod
    def update_stock(product_id: int, new_quantity: int,
                     admin_user) -> 'Product':
        """
        Met à jour le stock d'un produit.
        Si new_quantity > 0 et le produit était SOLD_OUT → repasse ACTIVE.
        Crée une notification si stock remis en stock.
        """
        from apps.catalogue.models import Product
        product = get_object_or_404(Product, pk=product_id)
        old_qty = product.stock_quantity

        product.stock_quantity = new_quantity
        if new_quantity > 0 and product.status == 'sold_out':
            product.status = 'active'

        product.save(update_fields=['stock_quantity', 'status', 'updated_at'])

        # Notifier si remise en stock
        if old_qty == 0 and new_quantity > 0:
            NotificationService.create(
                notif_type  = InternalNotification.NotifType.STOCK_LOW,
                title       = f"Réapprovisionnement : {product.title}",
                message     = (
                    f"Le produit \"{product.title}\" a été "
                    f"réapprovisionné ({new_quantity} unités) "
                    f"par {admin_user.full_name}."
                ),
                priority       = InternalNotification.NotifPriority.LOW,
                related_product = product,
            )
        return product

    @staticmethod
    def validate_product(product_id: int,
                         admin_user,
                         approved: bool,
                         note: str = '') -> 'Product':
        """
        Valide (active) ou rejette (archive) un produit artisan en DRAFT.
        """
        from apps.catalogue.models import Product
        product = get_object_or_404(Product, pk=product_id, status='draft')

        if approved:
            product.status = 'active'
            msg = f"Produit \"{product.title}\" approuvé par {admin_user.full_name}."
        else:
            product.status = 'archived'
            msg = f"Produit \"{product.title}\" rejeté. Motif : {note}"

        product.save(update_fields=['status', 'updated_at'])

        NotificationService.create(
            notif_type      = InternalNotification.NotifType.PRODUCT_SUBMIT,
            title           = msg,
            message         = note,
            priority        = InternalNotification.NotifPriority.LOW,
            related_product = product,
        )
        return product


class OrderAdminService:

    @staticmethod
    def validate_custom_order(
        order_id: int,
        admin_user,
        approved: bool,
        note: str = '',
    ) -> 'Order':
        """
        Valide ou rejette une commande personnalisée.
        """
        from apps.orders.models import Order
        from apps.orders.services import OrderService

        order = get_object_or_404(Order, pk=order_id)

        if order.status != 'paid':
            raise ValueError(
                f"La commande {order.reference} n'est pas en attente de validation "
                f"(statut actuel : {order.get_status_display()})."
            )

        if approved:
            OrderService.transition_status(
                order, 'confirmed', admin_user,
                note=f"Validée par {admin_user.full_name}. {note}"
            )
            OrderService.transition_status(
                order, 'in_craft', admin_user,
                note="Lancée en confection."
            )
            NotificationService.create(
                notif_type    = InternalNotification.NotifType.CUSTOM_ORDER,
                title         = f"Commande {order.reference} lancée en confection",
                message       = (
                    f"La commande personnalisée {order.reference} "
                    f"a été validée et lancée en confection."
                ),
                priority      = InternalNotification.NotifPriority.MEDIUM,
                related_order = order,
            )
        else:
            OrderService.transition_status(
                order, 'cancelled', admin_user,
                note=f"Rejetée par {admin_user.full_name}. Motif : {note}"
            )

        return order

    @staticmethod
    def get_orders_to_validate():
        """Commandes PAID avec au moins une CustomizationSession liée."""
        from apps.orders.models import Order
        return (
            Order.objects
            .filter(
                status='paid',
                items__customization_session__isnull=False
            )
            .distinct()
            .prefetch_related(
                'items__product',
                'items__customization_session',
                'items__artisan',
            )
            .select_related('user')
            .order_by('paid_at')
        )

    @staticmethod
    def get_all_orders(
        status: str = None,
        search: str = None,
        date_from=None,
        date_to=None,
    ):
        """Toutes les commandes avec filtres optionnels."""
        from apps.orders.models import Order
        qs = (
            Order.objects
            .select_related('user')
            .prefetch_related('items__product', 'payment_attempts')
            .order_by('-created_at')
        )
        if status:
            qs = qs.filter(status=status)
        if search:
            qs = qs.filter(
                Q(reference__icontains=search)
                | Q(user__email__icontains=search)
                | Q(delivery_name__icontains=search)
                | Q(delivery_phone__icontains=search)
            )
        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)
        return qs


class PromoService:

    @staticmethod
    def validate_and_apply_promo(
        code: str,
        order_amount: Decimal,
        user,
        category_ids: list[int] = None,
    ) -> dict:
        """Valide un code promo et calcule la réduction."""
        try:
            promo = PromoCode.objects.get(
                code__iexact=code, is_active=True
            )
        except PromoCode.DoesNotExist:
            return {
                'valid': False, 'discount': Decimal('0'),
                'message': "Code promo invalide ou expiré.", 'promo': None
            }

        if not promo.is_valid_now:
            return {
                'valid': False, 'discount': Decimal('0'),
                'message': "Ce code promo n'est plus valide.", 'promo': None
            }

        # Vérifier l'utilisation par cet utilisateur
        user_uses = promo.order_set.filter(
            user=user, status__in=['paid','confirmed','in_craft','shipped','delivered']
        ).count()
        if user_uses >= promo.max_uses_per_user:
            return {
                'valid': False, 'discount': Decimal('0'),
                'message': "Vous avez déjà utilisé ce code promo.", 'promo': None
            }

        # Vérifier restriction catégorie
        if promo.applicable_categories.exists() and category_ids:
            applicable_ids = set(
                promo.applicable_categories.values_list('pk', flat=True)
            )
            if not applicable_ids.intersection(set(category_ids)):
                return {
                    'valid': False, 'discount': Decimal('0'),
                    'message': (
                        "Ce code ne s'applique pas aux produits "
                        "de votre panier."
                    ),
                    'promo': None
                }

        discount = promo.compute_discount(order_amount)
        return {
            'valid':    True,
            'discount': discount,
            'message':  f"Code appliqué : -{discount:,.0f} FCFA",
            'promo':    promo,
        }

    @staticmethod
    def get_active_promo_banner() -> 'PromoCode | None':
        """Retourne le code promo actif avec un banner_text."""
        now = timezone.now()
        return (
            PromoCode.objects
            .filter(
                is_active    = True,
                valid_from__lte = now,
                valid_until__gte = now,
            )
            .exclude(banner_text='')
            .order_by('-valid_from')
            .first()
        )


class NotificationService:
    """Service centralisé de création de notifications internes."""

    @staticmethod
    def create(
        notif_type: str,
        title: str,
        message: str,
        priority: str = 'medium',
        action_url: str = '',
        related_order=None,
        related_product=None,
        related_artisan=None,
    ) -> 'InternalNotification':
        return InternalNotification.objects.create(
            type            = notif_type,
            title           = title,
            message         = message,
            priority        = priority,
            action_url      = action_url,
            related_order   = related_order,
            related_product = related_product,
            related_artisan = related_artisan,
        )

    @staticmethod
    def get_unread(limit: int = 20):
        return (
            InternalNotification.objects
            .filter(is_read=False)
            .select_related('related_order', 'related_product')
            .order_by('-created_at')[:limit]
        )
