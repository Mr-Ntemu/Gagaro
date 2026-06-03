from django.db import models
from django.utils.translation import gettext_lazy as _
from apps.core.models import TimeStampedModel
from decimal import Decimal
from .managers import OrderManager

class Cart(TimeStampedModel):
    """
    Panier persistant lié à un utilisateur connecté OU à une session anonyme.
    """
    user        = models.OneToOneField(
                    'accounts.KadoyaUser',
                    on_delete=models.CASCADE,
                    related_name='cart',
                    null=True, blank=True
                  )
    session_key = models.CharField(
                    max_length=40,
                    db_index=True,
                    blank=True,
                    help_text=_("Clé session Django pour paniers anonymes")
                  )

    class Meta:
        verbose_name        = _('Panier')
        verbose_name_plural = _('Paniers')
        constraints         = [
            models.UniqueConstraint(
                fields=['user'],
                condition=models.Q(user__isnull=False),
                name='unique_cart_per_user'
            )
        ]

    def __str__(self) -> str:
        owner = self.user.email if self.user else f"Anonyme ({self.session_key[:8]})"
        return f"Panier de {owner} ({self.total_items} article(s))"

    @property
    def total_items(self) -> int:
        return self.items.aggregate(total=models.Sum('quantity'))['total'] or 0

    @property
    def subtotal(self) -> Decimal:
        return sum(item.line_total for item in self.items.select_related('product'))

    @property
    def is_empty(self) -> bool:
        return not self.items.exists()


class CartItem(TimeStampedModel):
    """
    Ligne d'article dans le panier.
    """
    cart                   = models.ForeignKey(
                               Cart, on_delete=models.CASCADE, related_name='items'
                             )
    product                = models.ForeignKey(
                               'catalogue.Product', on_delete=models.CASCADE
                             )
    customization_session  = models.OneToOneField(
                               'customization.CustomizationSession',
                               on_delete=models.SET_NULL,
                               null=True, blank=True,
                               related_name='cart_item',
                               help_text=_("Rempli uniquement pour les produits personnalisés")
                             )
    quantity               = models.PositiveSmallIntegerField(default=1)
    unit_price             = models.DecimalField(
                               max_digits=10, decimal_places=2,
                               help_text=_("Prix snapshot au moment de l'ajout au panier")
                             )

    class Meta:
        verbose_name        = _('Article du panier')
        verbose_name_plural = _('Articles du panier')
        constraints         = [
            models.UniqueConstraint(
                fields=['cart', 'product'],
                condition=models.Q(customization_session__isnull=True),
                name='unique_standard_product_per_cart'
            )
        ]

    def __str__(self) -> str:
        suffix = " (personnalisé)" if self.customization_session else ""
        return f"{self.product.title}{suffix} × {self.quantity}"

    @property
    def line_total(self) -> Decimal:
        return self.unit_price * self.quantity

    @property
    def is_customized(self) -> bool:
        return self.customization_session is not None


class Order(TimeStampedModel):
    """
    Commande confirmée après paiement.
    """
    class OrderStatus(models.TextChoices):
        PENDING    = 'pending',    _('En attente de paiement')
        PAID       = 'paid',       _('Payée')
        CONFIRMED  = 'confirmed',  _('Confirmée par admin')
        IN_CRAFT   = 'in_craft',   _('En confection')
        SHIPPED    = 'shipped',    _('Expédiée')
        DELIVERED  = 'delivered',  _('Livrée')
        CANCELLED  = 'cancelled',  _('Annulée')
        REFUNDED   = 'refunded',   _('Remboursée')

    user            = models.ForeignKey(
                        'accounts.KadoyaUser',
                        on_delete=models.PROTECT,
                        related_name='orders'
                      )
    reference       = models.CharField(
                        max_length=20, unique=True, db_index=True,
                        help_text=_("Ex: KDY-20241205-0042")
                      )
    status          = models.CharField(
                        max_length=20,
                        choices=OrderStatus.choices,
                        default=OrderStatus.PENDING
                      )
    subtotal        = models.DecimalField(max_digits=10, decimal_places=2)
    delivery_fee    = models.DecimalField(
                        max_digits=8, decimal_places=2, default=Decimal('0.00')
                      )
    discount_amount = models.DecimalField(
                        max_digits=8, decimal_places=2, default=Decimal('0.00'),
                        help_text=_("Montant déduit par code promo (Sprint 7)")
                      )
    total_amount    = models.DecimalField(max_digits=10, decimal_places=2)

    delivery_name     = models.CharField(max_length=200)
    delivery_phone    = models.CharField(max_length=20)
    delivery_address  = models.TextField()
    delivery_city     = models.CharField(max_length=100)
    delivery_notes    = models.TextField(
                          blank=True,
                          help_text=_("Instructions de livraison spéciales")
                        )
    payment_method    = models.CharField(max_length=50, blank=True)
    payment_reference = models.CharField(max_length=200, blank=True, db_index=True)
    paid_at           = models.DateTimeField(null=True, blank=True)
    promo_code        = models.CharField(max_length=50, blank=True)

    objects = OrderManager()

    class Meta:
        verbose_name        = _('Commande')
        verbose_name_plural = _('Commandes')
        ordering            = ['-created_at']
        indexes             = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['user', 'status']),
        ]

    def __str__(self) -> str:
        return f"Commande {self.reference} — {self.get_status_display()}"

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = self._generate_reference()
        super().save(*args, **kwargs)

    @staticmethod
    def _generate_reference() -> str:
        from django.utils import timezone
        today    = timezone.now().strftime('%Y%m%d')
        prefix   = f"KDY-{today}-"
        last     = Order.objects.filter(
                     reference__startswith=prefix
                   ).order_by('-reference').first()
        sequence = int(last.reference[-4:]) + 1 if last else 1
        return f"{prefix}{sequence:04d}"

    @property
    def is_cancellable(self) -> bool:
        return self.status in [Order.OrderStatus.PENDING, Order.OrderStatus.PAID]


class OrderItem(TimeStampedModel):
    """Ligne d'article dans une commande."""
    order                 = models.ForeignKey(
                              Order, on_delete=models.CASCADE, related_name='items'
                            )
    product               = models.ForeignKey(
                              'catalogue.Product', on_delete=models.PROTECT
                            )
    customization_session = models.ForeignKey(
                              'customization.CustomizationSession',
                              on_delete=models.SET_NULL,
                              null=True, blank=True
                            )
    artisan               = models.ForeignKey(
                              'accounts.KadoyaUser',
                              on_delete=models.PROTECT,
                              related_name='order_items'
                            )
    product_title    = models.CharField(max_length=200)
    unit_price       = models.DecimalField(max_digits=10, decimal_places=2)
    quantity         = models.PositiveSmallIntegerField(default=1)
    line_total       = models.DecimalField(max_digits=10, decimal_places=2)
    commission_rate  = models.DecimalField(
                         max_digits=5, decimal_places=2, default=Decimal('15.00')
                       )
    artisan_payout   = models.DecimalField(
                         max_digits=10, decimal_places=2
                       )

    class Meta:
        verbose_name        = _('Article commandé')
        verbose_name_plural = _('Articles commandés')

    def __str__(self) -> str:
        return f"{self.product_title} × {self.quantity} (Commande {self.order.reference})"


class OrderStatusHistory(models.Model):
    """Historique des changements de statut."""
    order      = models.ForeignKey(
                   Order, on_delete=models.CASCADE, related_name='status_history'
                 )
    old_status = models.CharField(max_length=20, blank=True)
    new_status = models.CharField(max_length=20)
    changed_by = models.ForeignKey(
                   'accounts.KadoyaUser',
                   on_delete=models.SET_NULL,
                   null=True, blank=True
                 )
    note       = models.TextField(blank=True)
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = _('Historique statut')
        verbose_name_plural = _('Historique statuts')
        ordering            = ['-changed_at']

    def __str__(self) -> str:
        return f"{self.order.reference} : {self.old_status} → {self.new_status}"
