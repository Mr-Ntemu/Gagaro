"""
Interface publique du moteur de recommandation.
"""

import logging
from django.core.cache import cache

from .engine import RecommendationEngine
from .models import BehaviorEvent, RecommendationCache

logger = logging.getLogger(__name__)


class RecommendationService:

    CACHE_TTL_SECONDS  = 7200   # 2 heures
    COLD_START_LIMIT   = 3      # Nb événements minimum pour personnaliser

    @staticmethod
    def get_recommendations(
        user,
        context: str = 'home',
        limit: int = 8,
        exclude_product_ids: list[int] = None,
        category_ids: list[int] = None,
        use_cache: bool = True,
    ) -> list:
        """
        Point d'entrée principal pour obtenir des recommandations.
        """
        from apps.catalogue.models import Product

        # Cold start : pas assez de données
        event_count = BehaviorEvent.objects.filter(user=user).count()
        if event_count < RecommendationService.COLD_START_LIMIT:
            logger.debug(
                f"[Reco] Cold start pour {user.email} "
                f"({event_count} événements)"
            )
            return RecommendationEngine._get_fallback_recommendations(limit)

        # Clé cache Django
        cache_key = (
            f"reco_{user.pk}_{context}_"
            f"{'_'.join(map(str, sorted(exclude_product_ids or [])))}"
        )

        if use_cache:
            cached_ids = cache.get(cache_key)
            if cached_ids is not None:
                products = list(
                    Product.objects.active()
                    .filter(pk__in=cached_ids)
                    .prefetch_related('images')
                    .select_related('category')
                )
                # Réordonner selon l'ordre du cache
                order_map = {pid: i for i, pid in enumerate(cached_ids)}
                return sorted(products, key=lambda p: order_map.get(p.pk, 999))

        # Calcul via le moteur
        try:
            engine   = RecommendationEngine(user)
            products = engine.compute_recommendations(
                context             = context,
                exclude_product_ids = exclude_product_ids,
                category_ids        = category_ids,
                limit               = limit,
            )

            # Mettre en cache
            if use_cache and products:
                product_ids = [p.pk for p in products]
                cache.set(cache_key, product_ids, RecommendationService.CACHE_TTL_SECONDS)

            return products

        except Exception as e:
            logger.exception(f"[Reco] Erreur moteur pour {user.email} : {e}")
            return RecommendationEngine._get_fallback_recommendations(limit)

    @staticmethod
    def track_event(
        user,
        product,
        event_type: str,
    ) -> None:
        """
        Enregistre un événement comportemental en DB.
        """
        try:
            BehaviorEvent.objects.get_or_create(
                user       = user,
                product    = product,
                event_type = event_type,
                defaults   = {
                    'category_id':   product.category_id,
                    'tags_snapshot': product.tags or '',
                }
            )

            # Invalider le cache après événement majeur
            if event_type in ['purchase', 'review_pos', 'review_neg']:
                RecommendationService._invalidate_cache(user)
                # Déclencher rebuild profil en arrière-plan
                RecommendationService._schedule_profile_rebuild(user)

        except Exception as e:
            # Ne jamais bloquer une action client pour une erreur de tracking
            logger.warning(f"[Reco] Erreur tracking {event_type} : {e}")

    @staticmethod
    def flush_session_events(user, request) -> None:
        """
        Persiste les événements comportementaux accumulés dans la session.
        """
        from apps.catalogue.models import Product

        session_maps = [
            ('viewed_products',     'view'),
            ('cart_products',       'cart'),
            ('customized_products', 'customize'),
        ]

        events_created = 0
        for session_key, event_type in session_maps:
            items = request.session.get(session_key, [])
            for item in items:
                product_id = (
                    item if isinstance(item, int)
                    else item.get('product_id')
                )
                if not product_id:
                    continue
                try:
                    product = Product.objects.get(pk=product_id, status='active')
                    _, created = BehaviorEvent.objects.get_or_create(
                        user       = user,
                        product    = product,
                        event_type = event_type,
                        defaults   = {
                            'category_id':   product.category_id,
                            'tags_snapshot': product.tags or '',
                        }
                    )
                    if created:
                        events_created += 1
                except Product.DoesNotExist:
                    pass

        if events_created > 0:
            logger.debug(
                f"[Reco] {events_created} événements session flushés "
                f"pour {user.email}"
            )

    @staticmethod
    def _invalidate_cache(user) -> None:
        """Invalide tous les caches de recommandation de l'utilisateur."""
        for context in ['home', 'product', 'cart', 'global']:
            cache.delete(f"reco_{user.pk}_{context}_")

        # Marquer les caches DB comme stale
        RecommendationCache.objects.filter(
            user=user
        ).update(is_stale=True)

    @staticmethod
    def _schedule_profile_rebuild(user) -> None:
        """
        Déclenche le rebuild du profil client en arrière-plan.
        """
        try:
            engine = RecommendationEngine(user)
            engine.rebuild_profile()
        except Exception as e:
            logger.warning(f"[Reco] Rebuild profil échoué pour {user.email} : {e}")

    @staticmethod
    def migrate_anonymous_events(request, user) -> None:
        """
        Transfère les événements comportementaux accumulés en session
        (utilisateur anonyme) vers les BehaviorEvent de l'utilisateur connecté.
        Appelé lors de la connexion pour construire le profil dès le départ.
        """
        from apps.catalogue.models import Product

        viewed_ids = request.session.get('viewed_products', [])
        if not viewed_ids:
            return

        events_created = 0
        for product_id in viewed_ids[-20:]:  # Limiter aux 20 derniers
            try:
                product = Product.objects.get(pk=product_id, status='active')
                _, created = BehaviorEvent.objects.get_or_create(
                    user       = user,
                    product    = product,
                    event_type = 'view',
                    defaults   = {
                        'category_id':   product.category_id,
                        'tags_snapshot': product.tags or '',
                    }
                )
                if created:
                    events_created += 1
            except Product.DoesNotExist:
                pass

        # Nettoyer la session
        if 'viewed_products' in request.session:
            del request.session['viewed_products']
            request.session.modified = True

        if events_created > 0:
            logger.info(
                f"[Reco] {events_created} événements anonymes migrés "
                f"pour {user.email}"
            )
            # Déclencher un rebuild du profil
            RecommendationService._schedule_profile_rebuild(user)


class AnonymousRecommendationService:
    """
    Recommandations pour les utilisateurs non connectés.
    """

    @staticmethod
    def get_recommendations(
        request,
        limit: int = 8,
        exclude_product_ids: list[int] = None,
    ) -> list:
        """
        Recommandations anonymes.
        """
        from apps.catalogue.models import Product

        viewed_ids = request.session.get('viewed_products', [])
        exclude    = set(exclude_product_ids or [])

        # Produits vus en session (filtrés)
        seen_products = []
        if viewed_ids:
            filtered_ids = [
                pid for pid in viewed_ids[-8:]
                if pid not in exclude
            ]
            seen_products = list(
                Product.objects.active()
                .filter(pk__in=filtered_ids)
                .prefetch_related('images')
                .select_related('category')
            )

        # Compléter avec les populaires si pas assez
        if len(seen_products) < limit:
            popular = list(
                Product.objects.active()
                .exclude(pk__in=exclude | {p.pk for p in seen_products})
                .prefetch_related('images')
                .order_by('-view_count')
                [:limit - len(seen_products)]
            )
            seen_products.extend(popular)

        return seen_products[:limit]
