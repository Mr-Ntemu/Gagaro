"""
Cœur du moteur de recommandation Kadoya.
"""

import logging
import math
from decimal import Decimal
from django.db.models import Sum, Count, Q, Avg, Case, When, IntegerField
from django.utils import timezone
from datetime import timedelta

from .scoring import (
    compute_event_score,
    compute_category_bonus,
    compute_tag_bonus,
    compute_collaborative_bonus,
    compute_price_affinity,
    normalize_scores,
)
from .models import BehaviorEvent, ClientProfile, RecommendationCache

logger = logging.getLogger(__name__)


class RecommendationEngine:
    """
    Moteur de recommandation principal de Kadoya.
    """

    # Paramètres du moteur
    MAX_CANDIDATES        = 200  # Nb produits candidats évalués
    LOOKBACK_DAYS         = 90   # Fenêtre temporelle d'analyse
    MALUS_ALREADY_BOUGHT  = -999.0
    MALUS_LOW_STOCK       = -10.0
    STOCK_LOW_THRESHOLD   = 1

    def __init__(self, user):
        self.user    = user
        self.profile = self._load_profile()

    # ── Profil client ──────────────────────────────────────────────────────────

    def _load_profile(self) -> 'ClientProfile':
        """Charge ou crée le profil de recommandation du client."""
        profile, _ = ClientProfile.objects.get_or_create(user=self.user)
        return profile

    def rebuild_profile(self) -> 'ClientProfile':
        """
        Reconstruit le profil de goût du client depuis ses BehaviorEvents.
        """
        since = timezone.now() - timedelta(days=self.LOOKBACK_DAYS)

        events = (
            BehaviorEvent.objects
            .filter(user=self.user, occurred_at__gte=since)
            .select_related('product__category')
        )

        category_scores: dict[str, float] = {}
        tag_scores:      dict[str, float] = {}
        prices_viewed:   list[float]      = []
        prices_purchased: list[float]     = []

        for event in events:
            score  = compute_event_score(event.weight, event.occurred_at)
            cat_id = str(event.category_id or event.product.category_id)

            # Catégorie
            category_scores[cat_id] = category_scores.get(cat_id, 0) + score

            # Tags
            for tag in (event.tags_snapshot or '').split(','):
                tag = tag.strip().lower()
                if tag:
                    tag_scores[tag] = tag_scores.get(tag, 0) + score

            # Prix
            price = float(event.product.effective_price)
            if event.event_type == 'view':
                prices_viewed.append(price)
            elif event.event_type == 'purchase':
                prices_purchased.append(price)

        self.profile.favorite_categories = category_scores
        self.profile.favorite_tags       = tag_scores
        self.profile.avg_price_viewed    = (
            Decimal(str(sum(prices_viewed) / len(prices_viewed)))
            if prices_viewed else None
        )
        self.profile.avg_price_purchased = (
            Decimal(str(sum(prices_purchased) / len(prices_purchased)))
            if prices_purchased else None
        )
        self.profile.last_rebuilt_at = timezone.now()
        self.profile.events_count    = events.count()
        self.profile.save()

        logger.info(
            f"Profil reco reconstruit pour {self.user.email} "
            f"({self.profile.events_count} événements analysés)"
        )
        return self.profile

    # ── Candidats ─────────────────────────────────────────────────────────────

    def _get_candidates(
        self,
        exclude_product_ids: list[int] = None,
        category_ids: list[int] = None,
    ) -> list:
        """
        Sélectionne les produits candidats à la recommandation.
        """
        from apps.catalogue.models import Product

        # Produits déjà achetés par le client
        already_bought = set(
            BehaviorEvent.objects
            .filter(user=self.user, event_type='purchase')
            .values_list('product_id', flat=True)
        )

        exclude_ids = already_bought | set(exclude_product_ids or [])

        qs = (
            Product.objects.active()
            .exclude(pk__in=exclude_ids)
            .select_related('category')
            .prefetch_related('images')
            .order_by('-view_count')   # pré-tri par popularité
        )

        if category_ids:
            qs = qs.filter(category_id__in=category_ids)

        # Prioriser les catégories préférées du client
        top_cats = self.profile.top_categories
        if top_cats and not category_ids:
            # Produits des catégories préférées en premier
            qs = qs.order_by(
                Case(
                    *[
                        When(category_id=cat_id, then=i)
                        for i, cat_id in enumerate(top_cats)
                    ],
                    default=len(top_cats),
                    output_field=IntegerField(),
                ),
                '-view_count'
            )

        return list(qs[:self.MAX_CANDIDATES])

    def _get_similar_users(self) -> list[int]:
        """
        Trouve les utilisateurs avec un comportement similaire.
        """
        client_purchases = set(
            BehaviorEvent.objects
            .filter(user=self.user, event_type='purchase')
            .values_list('product_id', flat=True)
        )

        if not client_purchases:
            return []

        similar = (
            BehaviorEvent.objects
            .filter(
                event_type = 'purchase',
                product_id__in = client_purchases,
            )
            .exclude(user=self.user)
            .values('user_id')
            .annotate(common_count=Count('product_id', distinct=True))
            .order_by('-common_count')[:50]
        )
        return [row['user_id'] for row in similar]

    def _get_collaborative_purchase_counts(
        self, similar_user_ids: list[int]
    ) -> dict[int, int]:
        """
        Compte combien d'utilisateurs similaires ont acheté chaque produit.
        """
        if not similar_user_ids:
            return {}

        rows = (
            BehaviorEvent.objects
            .filter(
                user_id__in=similar_user_ids,
                event_type='purchase',
            )
            .values('product_id')
            .annotate(count=Count('user_id', distinct=True))
        )
        return {row['product_id']: row['count'] for row in rows}

    # ── Pipeline de scoring ───────────────────────────────────────────────────

    def _score_product(
        self,
        product,
        user_events_map: dict,
        collab_counts: dict,
        similar_user_ids: list[int],
    ) -> float:
        """
        Calcule le score de recommandation d'un produit candidat.
        """
        score = 0.0

        # 1. Score comportemental direct (si le client a déjà interagi)
        events = user_events_map.get(product.pk, [])
        for event in events:
            score += compute_event_score(event.weight, event.occurred_at)

        # 2. Bonus catégorie préférée
        score += compute_category_bonus(
            product.category_id,
            self.profile.favorite_categories,
        )

        # 3. Bonus tags correspondants
        score += compute_tag_bonus(
            product.tag_list,
            self.profile.favorite_tags,
        )

        # 4. Bonus collaboratif
        score += compute_collaborative_bonus(
            product.pk,
            similar_user_ids,
            collab_counts,
        )

        # 5. Affinité prix
        score += compute_price_affinity(
            product.effective_price,
            self.profile.avg_price_viewed,
        )

        # 6. Malus stock bas
        if product.stock_quantity <= self.STOCK_LOW_THRESHOLD:
            score += self.MALUS_LOW_STOCK

        # 7. Bonus popularité légère (log du nb de vues)
        score += math.log1p(product.view_count) * 0.1

        return score

    def compute_recommendations(
        self,
        context: str = 'global',
        exclude_product_ids: list[int] = None,
        category_ids: list[int] = None,
        limit: int = 8,
    ) -> list:
        """
        Pipeline complet de recommandation.
        """
        # Récupérer les candidats
        candidates = self._get_candidates(exclude_product_ids, category_ids)

        if not candidates:
            return self._get_fallback_recommendations(limit)

        # Charger les événements du client pour ces candidats
        candidate_ids = [p.pk for p in candidates]
        since         = timezone.now() - timedelta(days=self.LOOKBACK_DAYS)

        user_events = (
            BehaviorEvent.objects
            .filter(
                user       = self.user,
                product_id__in = candidate_ids,
                occurred_at__gte = since,
            )
        )
        # Grouper par product_id pour accès O(1) dans la boucle de scoring
        user_events_map: dict[int, list] = {}
        for event in user_events:
            user_events_map.setdefault(event.product_id, []).append(event)

        # Utilisateurs similaires + leurs achats
        similar_user_ids  = self._get_similar_users()
        collab_counts     = self._get_collaborative_purchase_counts(
                              similar_user_ids
                            )

        # Scorer tous les candidats
        scored = {}
        for product in candidates:
            scored[product.pk] = self._score_product(
                product, user_events_map, collab_counts, similar_user_ids
            )

        # Trier et retourner les top-N
        top_ids = sorted(
            scored, key=scored.get, reverse=True
        )[:limit]

        # Reconstituer dans l'ordre des scores
        products_map = {p.pk: p for p in candidates}
        result = [
            products_map[pid]
            for pid in top_ids
            if pid in products_map and scored[pid] > 0
        ]

        logger.debug(
            f"[Reco] {self.user.email} | context={context} | "
            f"candidates={len(candidates)} | results={len(result)}"
        )
        return result

    @staticmethod
    def _get_fallback_recommendations(limit: int = 8) -> list:
        """
        Recommandations de repli si pas assez de données comportementales.
        """
        from apps.catalogue.models import Product
        return list(
            Product.objects.active()
            .prefetch_related('images')
            .order_by('-view_count', '-created_at')[:limit]
        )
