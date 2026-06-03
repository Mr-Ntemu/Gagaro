"""
Tâches de maintenance du moteur de recommandation.
"""

import logging
from django.utils import timezone
from datetime import timedelta
from .models import BehaviorEvent

logger = logging.getLogger(__name__)


def rebuild_all_profiles() -> dict:
    """
    Reconstruit le profil de recommandation de tous les clients actifs.
    """
    from apps.accounts.models import KadoyaUser
    from .engine import RecommendationEngine

    clients = (
        KadoyaUser.objects.filter(role='client', is_active=True)
        .only('pk', 'email', 'role')
    )

    stats = {'success': 0, 'failed': 0, 'skipped': 0}

    for user in clients:
        # Skiper les clients sans événements récents
        has_events = BehaviorEvent.objects.filter(
            user        = user,
            occurred_at__gte = timezone.now() - timedelta(days=90)
        ).exists()

        if not has_events:
            stats['skipped'] += 1
            continue

        try:
            engine = RecommendationEngine(user)
            engine.rebuild_profile()
            stats['success'] += 1
        except Exception as e:
            logger.error(f"[Reco] Rebuild échoué pour {user.email} : {e}")
            stats['failed'] += 1

    logger.info(f"[Reco] Rebuild terminé : {stats}")
    return stats


def cleanup_old_events(days_to_keep: int = 180) -> int:
    """
    Supprime les événements comportementaux de plus de N jours.
    """
    cutoff  = timezone.now() - timedelta(days=days_to_keep)
    deleted, _ = BehaviorEvent.objects.filter(occurred_at__lt=cutoff).delete()
    logger.info(f"[Reco] Cleanup : {deleted} événements supprimés (>{days_to_keep}j)")
    return deleted
