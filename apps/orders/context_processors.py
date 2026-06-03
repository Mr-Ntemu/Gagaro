from .models import Cart

def cart_context(request) -> dict:
    """
    Injecte le nombre d'articles du panier dans tous les templates.
    """
    count = 0
    try:
        if request.user.is_authenticated:
            cart = Cart.objects.filter(user=request.user).first()
            count = cart.total_items if cart else 0
        else:
            session_key = request.session.session_key
            if session_key:
                cart = Cart.objects.filter(
                    session_key=session_key, user__isnull=True
                ).first()
                count = cart.total_items if cart else 0
    except Exception:
        pass
    return {'cart_items_count': count}
