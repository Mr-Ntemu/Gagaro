from decimal import Decimal
from django.db import transaction as db_transaction
from django.db.models import Avg, Count, Q
from django.utils import timezone
from django.shortcuts import get_object_or_404
from apps.reviews.models import Review, ReviewPhoto
from apps.catalogue.models import Product

class ReviewService:

    @staticmethod
    def can_review(user, product: Product) -> dict:
        """
        Vérifie si un utilisateur peut laisser un avis sur un produit.

        Conditions requises :
        1. L'utilisateur a commandé ce produit
        2. La commande est DELIVERED
        3. L'utilisateur n'a pas encore laissé d'avis pour ce produit
        """
        from apps.orders.models import Order, OrderItem

        # Déjà un avis ?
        if Review.objects.filter(user=user, product=product).exists():
            return {
                'allowed': False,
                'reason':  "Vous avez déjà laissé un avis sur ce produit.",
                'order':   None, 'order_item': None,
            }

        # Commande DELIVERED contenant ce produit ?
        delivered_item = (
            OrderItem.objects
            .filter(
                order__user   = user,
                product       = product,
                order__status = 'delivered',
            )
            .select_related('order')
            .first()
        )

        if not delivered_item:
            return {
                'allowed': False,
                'reason':  (
                    "Vous ne pouvez laisser un avis que sur un produit "
                    "que vous avez reçu."
                ),
                'order':      None,
                'order_item': None,
            }

        return {
            'allowed':    True,
            'reason':     None,
            'order':      delivered_item.order,
            'order_item': delivered_item,
        }

    @staticmethod
    @db_transaction.atomic
    def create_review(
        user,
        product: Product,
        form_data: dict,
        photos: list,
    ) -> Review:
        """
        Crée un avis + ses photos.
        """
        check = ReviewService.can_review(user, product)
        if not check['allowed']:
            raise PermissionError(check['reason'])

        if len(photos) > 3:
            raise ValueError("Maximum 3 photos par avis.")

        # Créer l'avis
        review = Review.objects.create(
            user       = user,
            product    = product,
            order      = check['order'],
            order_item = check['order_item'],
            rating     = form_data['rating'],
            title      = form_data.get('title', ''),
            body       = form_data['body'],
            status     = Review.ModerationStatus.PENDING,
        )

        # Créer les photos
        for i, photo_file in enumerate(photos):
            ReviewPhoto.objects.create(
                review = review,
                image  = photo_file,
                order  = i,
            )

        # Notifier l'admin (InternalNotification)
        try:
            from apps.dashboard.services import NotificationService
            from apps.dashboard.models import InternalNotification
            NotificationService.create(
                notif_type      = InternalNotification.NotifType.REVIEW_REPORT,
                title           = f"Avis à modérer : {product.title}",
                message         = (
                    f"{user.full_name} a laissé un avis "
                    f"{review.rating}★ sur \"{product.title}\"."
                ),
                priority        = InternalNotification.NotifPriority.LOW,
                action_url      = f"/kadmin/avis/moderation/",
                related_product = product,
            )
        except Exception:
            pass  # Ne pas bloquer la création d'avis si la notif échoue

        return review

    @staticmethod
    @db_transaction.atomic
    def approve_review(
        review_id: int,
        admin_user,
    ) -> Review:
        """
        Approuve un avis et met à jour les stats du produit.
        """
        review = get_object_or_404(
            Review, pk=review_id, status='pending'
        )
        review.status       = Review.ModerationStatus.APPROVED
        review.moderated_by = admin_user
        review.moderated_at = timezone.now()
        review.save(update_fields=[
            'status', 'moderated_by', 'moderated_at'
        ])

        # Mettre à jour les stats du produit
        ReviewService._refresh_product_stats(review.product)
        return review

    @staticmethod
    @db_transaction.atomic
    def reject_review(
        review_id: int,
        admin_user,
        note: str,
    ) -> Review:
        """Rejette un avis avec un motif."""
        review = get_object_or_404(
            Review, pk=review_id, status='pending'
        )
        review.status         = Review.ModerationStatus.REJECTED
        review.moderated_by   = admin_user
        review.moderated_at   = timezone.now()
        review.rejection_note = note
        review.save(update_fields=[
            'status', 'moderated_by', 'moderated_at', 'rejection_note'
        ])
        return review

    @staticmethod
    def _refresh_product_stats(product: Product) -> None:
        """
        Recalcule les statistiques d'avis d'un produit.
        """
        from django.core.cache import cache
        stats = (
            Review.objects.approved()
            .filter(product=product)
            .aggregate(
                avg   = Avg('rating'),
                count = Count('pk'),
            )
        )
        cache.set(
            f'product_stats_{product.pk}',
            {
                'avg_rating':   round(stats['avg'] or 0, 1),
                'review_count': stats['count'] or 0,
            },
            timeout = 3600  # 1h
        )

    @staticmethod
    def get_product_stats(product: Product) -> dict:
        """
        Retourne les stats d'avis d'un produit depuis le cache.
        """
        from django.core.cache import cache
        key   = f'product_stats_{product.pk}'
        stats = cache.get(key)
        if stats is None:
            ReviewService._refresh_product_stats(product)
            stats = cache.get(key) or {'avg_rating': 0, 'review_count': 0}
        return stats

    @staticmethod
    def get_rating_distribution(product: Product) -> dict:
        """
        Distribution des notes pour une page produit.
        """
        approved = Review.objects.approved().filter(product=product)
        dist     = {i: 0 for i in range(5, 0, -1)}
        for row in approved.values('rating').annotate(count=Count('pk')):
            dist[row['rating']] = row['count']
        return dist

    @staticmethod
    def add_artisan_reply(
        review_id: int,
        artisan,
        reply_text: str,
    ) -> Review:
        """
        Permet à l'artisan de répondre à un avis approuvé sur son produit.
        """
        review = get_object_or_404(
            Review,
            pk             = review_id,
            product__artisan = artisan,
            status         = 'approved',
        )
        if review.artisan_reply:
            raise ValueError("Vous avez déjà répondu à cet avis.")

        review.artisan_reply      = reply_text.strip()
        review.artisan_replied_at = timezone.now()
        review.save(update_fields=['artisan_reply', 'artisan_replied_at'])
        return review


class OrderTrackingService:

    # Délais estimés par statut (en jours ouvrés)
    ESTIMATED_DELAYS = {
        'paid':      (1, 2),   # 1-2 jours pour validation admin
        'confirmed': (1, 1),   # 1 jour pour lancement confection
        'in_craft':  (3, 7),   # 3-7 jours de confection
        'shipped':   (1, 3),   # 1-3 jours de livraison
        'delivered': (0, 0),   # Livré
    }

    @staticmethod
    def get_tracking_data(order) -> dict:
        """
        Construit les données de suivi de commande pour le template.
        """
        from apps.orders.models import OrderStatusHistory

        # Définition des étapes de la timeline
        steps = [
            {
                'key':         'pending',
                'label':       'Commande passée',
                'description': 'Votre commande a été enregistrée.',
                'icon':        'bi-bag-check',
            },
            {
                'key':         'paid',
                'label':       'Paiement confirmé',
                'description': 'Votre paiement a été reçu.',
                'icon':        'bi-credit-card-2-front',
            },
            {
                'key':         'confirmed',
                'label':       'Validée',
                'description': 'Votre commande a été validée par notre équipe.',
                'icon':        'bi-patch-check',
            },
            {
                'key':         'in_craft',
                'label':       'En confection',
                'description': 'L\'artisan travaille sur votre création.',
                'icon':        'bi-tools',
            },
            {
                'key':         'shipped',
                'label':       'Expédiée',
                'description': 'Votre commande est en route.',
                'icon':        'bi-truck',
            },
            {
                'key':         'delivered',
                'label':       'Livrée',
                'description': 'Votre commande a été livrée. Merci !',
                'icon':        'bi-house-check',
            },
        ]

        # Map statut → index
        STATUS_INDEX = {
            'pending': 0, 'paid': 1, 'confirmed': 2,
            'in_craft': 3, 'shipped': 4, 'delivered': 5,
            'cancelled': -1,
        }
        current_idx = STATUS_INDEX.get(order.status, 0)

        # Enrichir les étapes avec les dates depuis l'historique
        history = {
            h.new_status: h.changed_at
            for h in order.status_history.all()
        }
        # Ajouter created_at pour l'étape 'pending'
        history['pending'] = order.created_at

        for i, step in enumerate(steps):
            step['completed']  = i < current_idx
            step['active']     = i == current_idx
            step['date']       = history.get(step['key'])
            step['pending']    = i > current_idx

        # Estimation de livraison
        estimated = None
        if order.status not in ['delivered', 'cancelled']:
            delays = OrderTrackingService.ESTIMATED_DELAYS.get(order.status)
            if delays and order.paid_at:
                from datetime import timedelta
                min_d = order.paid_at + timedelta(
                    days=sum(v[0] for k, v in
                             OrderTrackingService.ESTIMATED_DELAYS.items()
                             if STATUS_INDEX.get(k, 99) >= current_idx)
                )
                max_d = order.paid_at + timedelta(
                    days=sum(v[1] for k, v in
                             OrderTrackingService.ESTIMATED_DELAYS.items()
                             if STATUS_INDEX.get(k, 99) >= current_idx)
                )
                estimated = f"{min_d.strftime('%d/%m')} — {max_d.strftime('%d/%m/%Y')}"

        # Articles reviewables (livrés + pas encore évalués)
        reviewable = []
        if order.status == 'delivered':
            for item in order.items.select_related('product'):
                already = Review.objects.filter(
                    user=order.user, product=item.product
                ).exists()
                if not already:
                    reviewable.append(item)

        return {
            'order':              order,
            'timeline':           steps,
            'current_step':       current_idx,
            'estimated_delivery': estimated,
            'can_review':         len(reviewable) > 0,
            'reviewable_items':   reviewable,
        }
