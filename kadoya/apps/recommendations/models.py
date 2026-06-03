from django.db import models
from django.utils import timezone
from apps.core.models import TimeStampedModel

class BehaviorEvent(models.Model):
    """
    Événement comportemental persistant d'un client.
    Chaque interaction significative avec un produit est enregistrée ici.
    C'est la source de vérité du moteur de recommandation.
    """

    class EventType(models.TextChoices):
        VIEW       = 'view',       'Vue produit'
        CART       = 'cart',       'Ajout au panier'
        CUSTOMIZE  = 'customize',  'Personnalisation'
        PURCHASE   = 'purchase',   'Achat confirmé'
        REVIEW_POS = 'review_pos', 'Avis positif (4-5★)'
        REVIEW_NEG = 'review_neg', 'Avis négatif (1-2★)'

    # Poids par type d'événement
    EVENT_WEIGHTS = {
        'view':       1,
        'cart':       3,
        'customize':  4,
        'purchase':   5,
        'review_pos': 3,
        'review_neg': -1,
    }

    user       = models.ForeignKey(
                   'accounts.KadoyaUser',
                   on_delete=models.CASCADE,
                   related_name='behavior_events',
                   db_index=True
                 )
    product    = models.ForeignKey(
                   'catalogue.Product',
                   on_delete=models.CASCADE,
                   related_name='behavior_events',
                   db_index=True
                 )
    event_type = models.CharField(
                   max_length=20, choices=EventType.choices, db_index=True
                 )
    occurred_at = models.DateTimeField(
                    auto_now_add=True, db_index=True
                  )

    # Métadonnées optionnelles
    category_id  = models.IntegerField(
                     null=True, blank=True,
                     help_text="Dénormalisé pour accélérer les requêtes agrégées"
                   )
    tags_snapshot = models.CharField(
                      max_length=500, blank=True,
                      help_text="Tags du produit au moment de l'événement"
                    )

    class Meta:
        verbose_name        = 'Événement comportemental'
        verbose_name_plural = 'Événements comportementaux'
        ordering            = ['-occurred_at']
        indexes             = [
            models.Index(fields=['user', 'event_type', 'occurred_at']),
            models.Index(fields=['product', 'event_type']),
            models.Index(fields=['user', 'product']),
        ]
        # Éviter les doublons de vue dans la même heure
        constraints         = [
            models.UniqueConstraint(
                fields   = ['user', 'product', 'event_type'],
                condition = models.Q(event_type='view'),
                name      = 'unique_view_per_user_product_hour',
            )
        ]

    def __str__(self) -> str:
        return (
            f"{self.user.email} — {self.get_event_type_display()} "
            f"— {self.product.title}"
        )

    @property
    def weight(self) -> int:
        return self.EVENT_WEIGHTS.get(self.event_type, 0)


class ClientProfile(TimeStampedModel):
    """
    Profil de goût d'un client, recalculé périodiquement.
    Stocke les préférences agrégées pour accélérer les recommandations.
    """

    user = models.OneToOneField(
             'accounts.KadoyaUser',
             on_delete=models.CASCADE,
             related_name='recommendation_profile'
           )

    # Catégories préférées (JSON : {category_id: score_float})
    favorite_categories = models.JSONField(
                            default=dict,
                            help_text="Ex: {1: 12.5, 3: 8.0} (category_id: score)"
                          )

    # Tags préférés (JSON : {tag: score_float})
    favorite_tags       = models.JSONField(
                            default=dict,
                            help_text="Ex: {'bois': 7.5, 'portrait': 5.0}"
                          )

    # Fourchette de prix préférée (médiane des produits achetés/vus)
    avg_price_viewed    = models.DecimalField(
                            max_digits=10, decimal_places=2,
                            null=True, blank=True
                          )
    avg_price_purchased = models.DecimalField(
                            max_digits=10, decimal_places=2,
                            null=True, blank=True
                          )

    # Timestamp dernier recalcul
    last_rebuilt_at     = models.DateTimeField(null=True, blank=True)

    # Nombre d'événements ayant servi au calcul
    events_count        = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = 'Profil client (reco)'

    def __str__(self) -> str:
        return f"Profil reco de {self.user.email}"

    @property
    def top_categories(self) -> list[int]:
        """IDs des 3 catégories préférées, triées par score décroissant."""
        return sorted(
            self.favorite_categories,
            key=lambda k: self.favorite_categories[k],
            reverse=True
        )[:3]

    @property
    def top_tags(self) -> list[str]:
        """Top 5 tags préférés."""
        return sorted(
            self.favorite_tags,
            key=lambda k: self.favorite_tags[k],
            reverse=True
        )[:5]


class RecommendationCache(models.Model):
    """
    Cache des recommandations pré-calculées par utilisateur.
    """

    class RecoContext(models.TextChoices):
        HOME     = 'home',    'Page d\'accueil'
        PRODUCT  = 'product', 'Page produit (similaires personnalisés)'
        CART     = 'cart',    'Page panier'
        GLOBAL   = 'global',  'Recommandations globales'

    user        = models.ForeignKey(
                    'accounts.KadoyaUser',
                    on_delete=models.CASCADE,
                    related_name='recommendation_caches'
                  )
    context     = models.CharField(
                    max_length=20, choices=RecoContext.choices
                  )
    # IDs des produits recommandés (JSON array, max 12)
    product_ids = models.JSONField(default=list)
    # Scores correspondants (pour debug/monitoring)
    scores      = models.JSONField(default=dict)

    computed_at = models.DateTimeField(auto_now=True)
    is_stale    = models.BooleanField(
                    default=False,
                    help_text="Marqué True après un événement majeur → recalcul prioritaire"
                  )

    class Meta:
        unique_together = [['user', 'context']]
        verbose_name    = 'Cache recommandations'

    def __str__(self) -> str:
        return f"Cache {self.context} — {self.user.email}"

    @property
    def is_expired(self) -> bool:
        """Cache expiré si > 2 heures ou marqué stale."""
        from datetime import timedelta
        if self.is_stale:
            return True
        return (timezone.now() - self.computed_at) > timedelta(hours=2)
