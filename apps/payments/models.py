from django.db import models
from django.utils.translation import gettext_lazy as _
from apps.core.models import TimeStampedModel

class PaymentAttempt(TimeStampedModel):
    """
    Enregistre chaque tentative de paiement pour une commande.
    """
    class AttemptStatus(models.TextChoices):
        INITIATED = 'initiated', _('Initié')
        PENDING   = 'pending',   _('En attente confirmation client')
        SUCCESS   = 'success',   _('Succès')
        FAILED    = 'failed',    _('Échec')
        TIMEOUT   = 'timeout',   _('Expiré')
        CANCELLED = 'cancelled', _('Annulé')

    order           = models.ForeignKey(
                        'orders.Order',
                        on_delete=models.CASCADE,
                        related_name='payment_attempts'
                      )
    user            = models.ForeignKey(
                        'accounts.KadoyaUser',
                        on_delete=models.CASCADE
                      )
    flw_tx_ref      = models.CharField(
                        max_length=100, unique=True, db_index=True,
                        help_text=_("tx_ref envoyé à Flutterwave = order.reference")
                      )
    flw_transaction_id = models.CharField(
                           max_length=100, blank=True, db_index=True,
                           help_text=_("ID transaction Flutterwave (reçu dans le webhook)")
                         )
    flw_ref         = models.CharField(
                        max_length=200, blank=True,
                        help_text=_("Référence interne Flutterwave")
                      )
    amount          = models.DecimalField(max_digits=10, decimal_places=2)
    currency        = models.CharField(max_length=5, default='XAF')
    payment_method  = models.CharField(
                        max_length=20,
                        choices=[('mtn', 'MTN Mobile Money'), ('orange', 'Orange Money')],
                        default='mtn'
                      )
    phone_number    = models.CharField(max_length=20)
    status          = models.CharField(
                        max_length=20,
                        choices=AttemptStatus.choices,
                        default=AttemptStatus.INITIATED
                      )
    flw_init_response  = models.JSONField(
                           null=True, blank=True,
                           help_text=_("Réponse JSON de l'appel d'initiation")
                         )
    flw_webhook_payload = models.JSONField(
                            null=True, blank=True,
                            help_text=_("Payload brut du webhook reçu")
                          )
    flw_verify_response = models.JSONField(
                            null=True, blank=True,
                            help_text=_("Réponse de l'appel de vérification")
                          )
    initiated_at    = models.DateTimeField(auto_now_add=True)
    confirmed_at    = models.DateTimeField(
                        null=True, blank=True,
                        help_text=_("Timestamp de confirmation paiement")
                      )

    class Meta:
        verbose_name        = _('Tentative de paiement')
        verbose_name_plural = _('Tentatives de paiement')
        ordering            = ['-initiated_at']
        indexes             = [
            models.Index(fields=['flw_tx_ref']),
            models.Index(fields=['status', 'initiated_at']),
        ]

    def __str__(self) -> str:
        return f"Paiement {self.flw_tx_ref} — {self.get_status_display()}"

    @property
    def is_successful(self) -> bool:
        return self.status == self.AttemptStatus.SUCCESS
