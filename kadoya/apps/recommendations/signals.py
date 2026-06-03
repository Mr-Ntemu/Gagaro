import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from .services import RecommendationService

logger = logging.getLogger(__name__)

@receiver(post_save, sender='orders.Order')
def track_purchase_events(sender, instance, **kwargs):
    """
    Après confirmation de paiement (status → 'paid'),
    enregistre un BehaviorEvent 'purchase' pour chaque article commandé.
    """
    if instance.status != 'paid':
        return

    for item in instance.items.select_related('product').all():
        try:
            RecommendationService.track_event(
                user       = instance.user,
                product    = item.product,
                event_type = 'purchase',
            )
        except Exception as e:
            logger.warning(f"[Reco] Track purchase échoué : {e}")


@receiver(post_save, sender='reviews.Review')
def track_review_events(sender, instance, **kwargs):
    """
    Après modération d'un avis (status → 'approved'),
    enregistre un BehaviorEvent 'review_pos' ou 'review_neg'.
    """
    if instance.status != 'approved':
        return

    event_type = 'review_pos' if instance.rating >= 4 else 'review_neg'
    try:
        RecommendationService.track_event(
            user       = instance.user,
            product    = instance.product,
            event_type = event_type,
        )
    except Exception as e:
        logger.warning(f"[Reco] Track review échoué : {e}")
