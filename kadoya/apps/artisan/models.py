from decimal import Decimal
from django.db import models
from apps.core.models import TimeStampedModel
from django.utils import timezone


class ArtisanProfile(TimeStampedModel):
    """
    Profil étendu d'un artisan Kadoya.
    Créé automatiquement à l'inscription si role=artisan (signal post_save).
    Contient les informations métier : atelier, spécialités, Mobile Money.
    """

    user            = models.OneToOneField(
                        'accounts.KadoyaUser',
                        on_delete=models.CASCADE,
                        related_name='artisan_profile',
                        limit_choices_to={'role': 'artisan'}
                      )

    # Informations atelier
    shop_name       = models.CharField(
                        max_length=200,
                        help_text="Nom de l'atelier ou boutique"
                      )
    shop_description = models.TextField(
                         blank=True,
                         help_text="Description courte de l'atelier (~200 mots)"
                       )
    shop_banner     = models.ImageField(
                        upload_to='artisans/banners/',
                        blank=True, null=True
                      )

    # Localisation
    city            = models.CharField(max_length=100, blank=True)
    quarter         = models.CharField(
                        max_length=200, blank=True,
                        help_text="Quartier / zone de l'atelier"
                      )

    # Spécialités (tags libres séparés par virgules)
    specialties     = models.CharField(
                        max_length=500, blank=True,
                        help_text="Ex: cadres bois, aquarelle, portraits"
                      )

    # Paiement des commissions (Mobile Money)
    payout_phone    = models.CharField(
                        max_length=20, blank=True,
                        help_text="Numéro Mobile Money pour recevoir les commissions"
                      )
    payout_operator = models.CharField(
                        max_length=10,
                        choices=[('mtn','MTN MoMo'), ('orange','Orange Money')],
                        blank=True
                      )

    # Statistiques globales (dénormalisées pour la perf, mises à jour par signal)
    total_sales_count  = models.PositiveIntegerField(default=0)
    total_revenue      = models.DecimalField(
                           max_digits=12, decimal_places=2, default=Decimal('0.00')
                         )
    total_commission   = models.DecimalField(
                           max_digits=12, decimal_places=2, default=Decimal('0.00'),
                           help_text="Total des commissions prélevées par Kadoya"
                         )
    total_payout       = models.DecimalField(
                           max_digits=12, decimal_places=2, default=Decimal('0.00'),
                           help_text="Montant net reversé à l'artisan"
                         )

    # Validation admin
    is_verified     = models.BooleanField(
                        default=False,
                        help_text="Compte artisan vérifié par l'équipe Kadoya"
                      )
    verified_at     = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name        = 'Profil artisan'
        verbose_name_plural = 'Profils artisans'

    def __str__(self) -> str:
        return f"{self.shop_name} ({self.user.email})"

    @property
    def net_balance(self) -> Decimal:
        """Solde net artisan = total_payout - déjà versé (TODO Sprint 7)."""
        return self.total_payout

    @property
    def specialty_list(self) -> list[str]:
        return [s.strip() for s in self.specialties.split(',') if s.strip()]


class WithdrawalRequest(TimeStampedModel):
    """
    Demande de retrait de gains par un artisan.
    Traitée manuellement par l'admin dans ce MVP (Sprint 7).
    """

    class WithdrawalStatus(models.TextChoices):
        PENDING   = 'pending',   'En attente'
        APPROVED  = 'approved',  'Approuvée'
        PROCESSED = 'processed', 'Versée'
        REJECTED  = 'rejected',  'Rejetée'

    artisan     = models.ForeignKey(
                    ArtisanProfile,
                    on_delete=models.CASCADE,
                    related_name='withdrawal_requests'
                  )
    amount      = models.DecimalField(max_digits=10, decimal_places=2)
    phone       = models.CharField(max_length=20)
    operator    = models.CharField(
                    max_length=10,
                    choices=[('mtn','MTN MoMo'), ('orange','Orange Money')]
                  )
    status      = models.CharField(
                    max_length=20,
                    choices=WithdrawalStatus.choices,
                    default=WithdrawalStatus.PENDING
                  )
    admin_note  = models.TextField(blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name        = 'Demande de retrait'
        verbose_name_plural = 'Demandes de retrait'
        ordering            = ['-created_at']

    def __str__(self) -> str:
        return (
            f"Retrait {self.amount} XAF — "
            f"{self.artisan.shop_name} ({self.get_status_display()})"
        )
