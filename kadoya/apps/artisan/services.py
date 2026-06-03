from decimal import Decimal
from django.db.models import Sum, Count, Avg, Q
from django.utils import timezone
from datetime import timedelta


class ArtisanService:

    @staticmethod
    def get_dashboard_kpis(artisan_user: 'KadoyaUser') -> dict:
        """
        Calcule les KPIs du dashboard artisan.
        Toutes les requêtes agrégées en une seule passe pour la performance.

        Retourne :
        {
          'products_active'   : int,
          'products_draft'    : int,
          'products_sold_out' : int,
          'orders_pending'    : int,     ← commandes PAID non encore IN_CRAFT
          'orders_in_craft'   : int,
          'orders_shipped'    : int,
          'revenue_total'     : Decimal,
          'revenue_month'     : Decimal, ← 30 derniers jours
          'revenue_week'      : Decimal, ← 7 derniers jours
          'payout_total'      : Decimal,
          'avg_order_value'   : Decimal,
          'top_product'       : Product | None,
        }
        """
        from apps.catalogue.models import Product
        from apps.orders.models import OrderItem, Order

        now        = timezone.now()
        week_ago   = now - timedelta(days=7)
        month_ago  = now - timedelta(days=30)

        # Produits
        products = Product.objects.filter(artisan=artisan_user)
        products_stats = products.aggregate(
            active   = Count('pk', filter=Q(status='active')),
            draft    = Count('pk', filter=Q(status='draft')),
            sold_out = Count('pk', filter=Q(status='sold_out')),
        )

        # OrderItems de cet artisan (commandes payées uniquement)
        paid_items = OrderItem.objects.filter(
            artisan=artisan_user,
            order__status__in=['paid','confirmed','in_craft','shipped','delivered']
        )

        revenue_agg = paid_items.aggregate(
            total = Sum('line_total'),
            month = Sum('line_total',
                        filter=Q(order__paid_at__gte=month_ago)),
            week  = Sum('line_total',
                        filter=Q(order__paid_at__gte=week_ago)),
            payout = Sum('artisan_payout'),
            avg    = Avg('line_total'),
        )

        # Commandes en cours
        orders_agg = Order.objects.filter(
            items__artisan=artisan_user
        ).distinct().aggregate(
            pending  = Count('pk', filter=Q(status='paid')),
            in_craft = Count('pk', filter=Q(status='in_craft')),
            shipped  = Count('pk', filter=Q(status='shipped')),
        )

        # Produit le plus vendu
        top = (paid_items.values('product__title', 'product__pk')
                         .annotate(total_qty=Sum('quantity'))
                         .order_by('-total_qty')
                         .first())

        return {
            'products_active':   products_stats['active']   or 0,
            'products_draft':    products_stats['draft']     or 0,
            'products_sold_out': products_stats['sold_out']  or 0,
            'orders_pending':    orders_agg['pending']       or 0,
            'orders_in_craft':   orders_agg['in_craft']      or 0,
            'orders_shipped':    orders_agg['shipped']       or 0,
            'revenue_total':     revenue_agg['total']  or Decimal('0'),
            'revenue_month':     revenue_agg['month']  or Decimal('0'),
            'revenue_week':      revenue_agg['week']   or Decimal('0'),
            'payout_total':      revenue_agg['payout'] or Decimal('0'),
            'avg_order_value':   revenue_agg['avg']    or Decimal('0'),
            'top_product':       top,
        }

    @staticmethod
    def get_artisan_sales(
        artisan_user: 'KadoyaUser',
        status_filter: str = None,
        date_from=None,
        date_to=None,
    ) -> 'QuerySet':
        """
        Retourne les OrderItems de l'artisan avec filtres optionnels.
        Précharge order + product pour éviter N+1.
        """
        from apps.orders.models import OrderItem

        qs = (OrderItem.objects
              .filter(artisan=artisan_user)
              .select_related('order', 'product', 'order__user')
              .order_by('-order__created_at'))

        if status_filter:
            qs = qs.filter(order__status=status_filter)
        if date_from:
            qs = qs.filter(order__created_at__gte=date_from)
        if date_to:
            qs = qs.filter(order__created_at__lte=date_to)

        return qs

    @staticmethod
    def get_monthly_revenue_chart(artisan_user: 'KadoyaUser') -> list[dict]:
        """
        Calcule le chiffre d'affaires mensuel des 12 derniers mois.
        Retourne une liste de 12 dicts pour le graphique JS :
        [{'month': 'Nov 2024', 'revenue': 45000, 'payout': 38250}, ...]
        """
        from apps.orders.models import OrderItem
        from django.db.models.functions import TruncMonth

        data = (
            OrderItem.objects
            .filter(
                artisan=artisan_user,
                order__status__in=['paid','confirmed','in_craft','shipped','delivered'],
                order__paid_at__gte=timezone.now() - timedelta(days=365),
            )
            .annotate(month=TruncMonth('order__paid_at'))
            .values('month')
            .annotate(
                revenue=Sum('line_total'),
                payout =Sum('artisan_payout'),
            )
            .order_by('month')
        )

        return [
            {
                'month':   item['month'].strftime('%b %Y'),
                'revenue': float(item['revenue'] or 0),
                'payout':  float(item['payout']  or 0),
            }
            for item in data
        ]


class FinancialService:

    @staticmethod
    def get_financial_summary(profile: 'ArtisanProfile') -> dict:
        """
        Résumé financier complet pour la page Financial.
        """
        pending_withdrawals = profile.withdrawal_requests.filter(
            status='pending'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')

        return {
            'total_revenue':       profile.total_revenue,
            'total_commission':    profile.total_commission,
            'total_payout':        profile.total_payout,
            'pending_withdrawals': pending_withdrawals,
            'available_balance':   profile.total_payout - pending_withdrawals,
        }
