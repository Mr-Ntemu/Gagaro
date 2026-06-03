from django.db.models.signals import post_save
from django.dispatch import receiver
from apps.dashboard.models import InternalNotification
from apps.dashboard.services import NotificationService

@receiver(post_save, sender='orders.Order')
def notify_on_order_paid(sender, instance, **kwargs):
    """
    Crée une notification quand une commande passe à PAID.
    Si la commande contient une CustomizationSession → notification haute priorité.
    """
    if instance.status != 'paid':
        return

    has_custom = instance.items.filter(
        customization_session__isnull=False
    ).exists()

    if has_custom:
        NotificationService.create(
            notif_type    = InternalNotification.NotifType.CUSTOM_ORDER,
            title         = f"Commande perso à valider : {instance.reference}",
            message       = (
                f"La commande {instance.reference} de "
                f"{instance.delivery_name} contient des articles "
                f"personnalisés et nécessite une validation."
            ),
            priority      = InternalNotification.NotifPriority.HIGH,
            action_url    = f"/kadmin/commandes/{instance.pk}/",
            related_order = instance,
        )
    else:
        NotificationService.create(
            notif_type    = InternalNotification.NotifType.ORDER_PAID,
            title         = f"Nouvelle commande payée : {instance.reference}",
            message       = f"Montant : {instance.total_amount:,.0f} FCFA",
            priority      = InternalNotification.NotifPriority.MEDIUM,
            action_url    = f"/kadmin/commandes/{instance.pk}/",
            related_order = instance,
        )


@receiver(post_save, sender='catalogue.Product')
def notify_on_product_submitted(sender, instance, created, **kwargs):
    """Notification quand un artisan soumet un nouveau produit (status=draft)."""
    if created and instance.status == 'draft':
        try:
            profile = instance.artisan.artisan_profile
        except Exception:
            profile = None

        NotificationService.create(
            notif_type      = InternalNotification.NotifType.PRODUCT_SUBMIT,
            title           = f"Produit à valider : {instance.title}",
            message         = (
                f"L'artisan {instance.artisan.full_name} "
                f"a soumis un nouveau produit pour validation."
            ),
            priority        = InternalNotification.NotifPriority.MEDIUM,
            action_url      = "/kadmin/produits/en-attente/",
            related_product = instance,
            related_artisan = profile,
        )


@receiver(post_save, sender='artisan.WithdrawalRequest')
def notify_on_withdrawal_request(sender, instance, created, **kwargs):
    """Notification quand un artisan soumet une demande de retrait."""
    if created:
        NotificationService.create(
            notif_type      = InternalNotification.NotifType.WITHDRAWAL,
            title           = (
                f"Retrait {instance.amount:,.0f} FCFA — "
                f"{instance.artisan.shop_name}"
            ),
            message         = (
                f"Via {instance.get_operator_display()} "
                f"au {instance.phone}"
            ),
            priority        = InternalNotification.NotifPriority.HIGH,
            action_url      = "/kadmin/artisans/retraits/",
            related_artisan = instance.artisan,
        )
