from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from decimal import Decimal
from apps.core.models import TimeStampedModel

class PromoCode(TimeStampedModel):
    """
    Code promotionnel applicable au checkout.
    Peut être lié à une occasion spéciale (Fête des mères, Tabaski, etc.)
    ou à une catégorie de produits spécifique.
    """

    class DiscountType(models.TextChoices):
        PERCENTAGE  = 'percentage',  'Pourcentage (%)'
        FIXED       = 'fixed',       'Montant fixe (FCFA)'
        FREE_SHIP   = 'free_ship',   'Livraison gratuite'

    class PromoOccasion(models.TextChoices):
        NONE        = '',               'Aucune occasion'
        FETE_MERES  = 'fete_meres',    "Fête des mères"
        FETE_PERES  = 'fete_peres',    "Fête des pères"
        TABASKI     = 'tabaski',       'Tabaski'
        NOEL        = 'noel',          'Noël'
        NOUVEL_AN   = 'nouvel_an',     'Nouvel An'
        SAINT_VAL   = 'saint_valentin','Saint-Valentin'
        CUSTOM      = 'custom',        'Personnalisée'

    # Identité
    code            = models.CharField(
                        max_length=50, unique=True,
                        help_text="Ex: FETE-MERES-2024"
                      )
    occasion        = models.CharField(
                        max_length=30,
                        choices=PromoOccasion.choices,
                        default=PromoOccasion.NONE,
                        blank=True
                      )
    description     = models.TextField(blank=True)
    banner_text     = models.CharField(
                        max_length=200, blank=True,
                        help_text="Texte affiché sur la bannière promotionnelle du site"
                      )

    # Réduction
    discount_type   = models.CharField(
                        max_length=20,
                        choices=DiscountType.choices,
                        default=DiscountType.PERCENTAGE
                      )
    discount_value  = models.DecimalField(
                        max_digits=8, decimal_places=2,
                        help_text="Valeur de la réduction (% ou FCFA selon discount_type)"
                      )
    min_order_amount = models.DecimalField(
                         max_digits=10, decimal_places=2,
                         default=Decimal('0.00'),
                         help_text="Montant minimum de commande pour appliquer le code"
                       )
    max_discount_cap = models.DecimalField(
                         max_digits=10, decimal_places=2,
                         null=True, blank=True,
                         help_text="Plafond de réduction max (pour les % sur grosses commandes)"
                       )

    # Restrictions
    applicable_categories = models.ManyToManyField(
                              'catalogue.Category',
                              blank=True,
                              help_text="Laisser vide = applicable sur tout le catalogue"
                            )
    max_uses        = models.PositiveIntegerField(
                        null=True, blank=True,
                        help_text="Nombre max d'utilisations. Vide = illimité"
                      )
    max_uses_per_user = models.PositiveSmallIntegerField(
                          default=1,
                          help_text="Nombre max d'utilisations par client unique"
                        )
    current_uses    = models.PositiveIntegerField(
                        default=0, editable=False
                      )

    # Validité
    valid_from      = models.DateTimeField()
    valid_until     = models.DateTimeField()
    is_active       = models.BooleanField(default=True)

    created_by      = models.ForeignKey(
                        'accounts.KadoyaUser',
                        on_delete=models.SET_NULL,
                        null=True,
                        related_name='created_promos'
                      )

    class Meta:
        verbose_name        = 'Code promo'
        verbose_name_plural = 'Codes promo'
        ordering            = ['-valid_from']
        indexes             = [
            models.Index(fields=['code', 'is_active']),
        ]

    def __str__(self) -> str:
        return f"{self.code} ({self.get_discount_type_display()})"

    @property
    def is_valid_now(self) -> bool:
        """Vérifie si le code est utilisable à l'instant présent."""
        now = timezone.now()
        return (
            self.is_active
            and self.valid_from <= now <= self.valid_until
            and (self.max_uses is None or self.current_uses < self.max_uses)
        )

    @property
    def usage_percentage(self) -> float | None:
        """% d'utilisation par rapport au max_uses."""
        if not self.max_uses:
            return None
        return round((self.current_uses / self.max_uses) * 100, 1)

    def compute_discount(self, order_amount: Decimal) -> Decimal:
        """
        Calcule le montant de réduction applicable à une commande.
        Tient compte du plafond max_discount_cap.
        Retourne 0 si la commande n'atteint pas min_order_amount.
        """
        if order_amount < self.min_order_amount:
            return Decimal('0.00')

        if self.discount_type == self.DiscountType.FIXED:
            discount = min(self.discount_value, order_amount)

        elif self.discount_type == self.DiscountType.PERCENTAGE:
            discount = order_amount * (self.discount_value / 100)
            if self.max_discount_cap:
                discount = min(discount, self.max_discount_cap)

        else:  # FREE_SHIP
            discount = Decimal('0.00')  # Géré séparément sur les frais de livraison

        return discount.quantize(Decimal('0.01'))


class InternalNotification(TimeStampedModel):
    """
    Notification interne pour l'équipe admin.
    Générée automatiquement par des signaux (stock bas, retrait, etc.)
    """

    class NotifType(models.TextChoices):
        STOCK_LOW      = 'stock_low',      '⚠️ Stock bas'
        ORDER_PAID     = 'order_paid',     '💰 Commande payée'
        CUSTOM_ORDER   = 'custom_order',   '🎨 Commande perso à valider'
        WITHDRAWAL     = 'withdrawal',     '💳 Demande de retrait'
        ARTISAN_SIGNUP = 'artisan_signup', '👤 Nouvel artisan'
        REVIEW_REPORT  = 'review_report',  '🚨 Avis signalé'
        PRODUCT_SUBMIT = 'product_submit', '📦 Produit soumis'

    class NotifPriority(models.TextChoices):
        LOW    = 'low',    'Basse'
        MEDIUM = 'medium', 'Moyenne'
        HIGH   = 'high',   'Haute'

    type        = models.CharField(max_length=30, choices=NotifType.choices)
    priority    = models.CharField(
                    max_length=10,
                    choices=NotifPriority.choices,
                    default=NotifPriority.MEDIUM
                  )
    title       = models.CharField(max_length=200)
    message     = models.TextField()
    action_url  = models.CharField(
                    max_length=500, blank=True,
                    help_text="URL vers laquelle pointe le bouton d'action"
                  )
    is_read     = models.BooleanField(default=False)
    read_by     = models.ForeignKey(
                    'accounts.KadoyaUser',
                    on_delete=models.SET_NULL,
                    null=True, blank=True,
                    related_name='read_notifications'
                  )
    read_at     = models.DateTimeField(null=True, blank=True)

    # Référence optionnelle à un objet métier
    related_order   = models.ForeignKey(
                        'orders.Order', on_delete=models.SET_NULL,
                        null=True, blank=True
                      )
    related_product = models.ForeignKey(
                        'catalogue.Product', on_delete=models.SET_NULL,
                        null=True, blank=True
                      )
    related_artisan = models.ForeignKey(
                        'artisan.ArtisanProfile', on_delete=models.SET_NULL,
                        null=True, blank=True
                      )

    class Meta:
        verbose_name        = 'Notification interne'
        verbose_name_plural = 'Notifications internes'
        ordering            = ['-created_at']
        indexes             = [
            models.Index(fields=['is_read', 'priority', 'created_at']),
        ]

    def __str__(self) -> str:
        return f"[{self.get_type_display()}] {self.title}"

    def mark_as_read(self, admin_user) -> None:
        if not self.is_read:
            self.is_read  = True
            self.read_by  = admin_user
            self.read_at  = timezone.now()
            self.save(update_fields=['is_read', 'read_by', 'read_at'])


class ReviewReport(TimeStampedModel):
    """
    Signalement d'un avis client par un artisan ou un autre client.
    Les avis sont créés au Sprint 8 ; ce modèle prépare leur modération.
    """

    class ReportReason(models.TextChoices):
        SPAM        = 'spam',       'Spam / faux avis'
        OFFENSIVE   = 'offensive',  'Contenu offensant'
        IRRELEVANT  = 'irrelevant', 'Hors sujet'
        FAKE        = 'fake',       'Avis falsifié'
        OTHER       = 'other',      'Autre'

    class ReportStatus(models.TextChoices):
        PENDING  = 'pending',  'En attente'
        APPROVED = 'approved', 'Avis conservé'
        REMOVED  = 'removed',  'Avis supprimé'

    # review = models.ForeignKey('reviews.Review', ...)  ← TODO Sprint 8
    review_id   = models.PositiveIntegerField(
                    help_text="ID de l'avis signalé (FK vers Review — Sprint 8)"
                  )
    reported_by = models.ForeignKey(
                    'accounts.KadoyaUser',
                    on_delete=models.CASCADE,
                    related_name='review_reports'
                  )
    reason      = models.CharField(max_length=20, choices=ReportReason.choices)
    details     = models.TextField(blank=True)
    status      = models.CharField(
                    max_length=20,
                    choices=ReportStatus.choices,
                    default=ReportStatus.PENDING
                  )
    resolved_by = models.ForeignKey(
                    'accounts.KadoyaUser',
                    on_delete=models.SET_NULL,
                    null=True, blank=True,
                    related_name='resolved_reports'
                  )
    resolved_at = models.DateTimeField(null=True, blank=True)
    admin_note  = models.TextField(blank=True)

    class Meta:
        verbose_name        = 'Signalement avis'
        verbose_name_plural = 'Signalements avis'
        ordering            = ['-created_at']
