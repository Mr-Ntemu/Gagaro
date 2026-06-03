from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from .models import Cart
from .services import CartService

@receiver(user_logged_in)
def merge_anonymous_cart_on_login(sender, request, user, **kwargs):
    """
    Après chaque login, fusionne le panier anonyme (session)
    dans le panier utilisateur.
    """
    session_key = request.session.session_key
    if not session_key:
        return

    try:
        anonymous_cart = Cart.objects.get(
            session_key=session_key, user__isnull=True
        )
        user_cart, _ = Cart.objects.get_or_create(user=user)

        if not anonymous_cart.is_empty:
            CartService.merge_carts(anonymous_cart, user_cart)

    except Cart.DoesNotExist:
        pass
