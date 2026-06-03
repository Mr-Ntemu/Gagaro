from decimal import Decimal
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.utils import timezone
from apps.catalogue.models import Product
from apps.customization.models import CustomizationSession
from .models import Cart, CartItem, Order, OrderItem, OrderStatusHistory

class CartService:

    @staticmethod
    def get_or_create_cart(request) -> Cart:
        if request.user.is_authenticated:
            cart, _ = Cart.objects.get_or_create(user=request.user)
            return cart
        
        if not request.session.session_key:
            request.session.create()
        
        session_key = request.session.session_key
        cart, _ = Cart.objects.get_or_create(session_key=session_key, user__isnull=True)
        return cart

    @staticmethod
    def add_item(
        cart: Cart,
        product: Product,
        quantity: int = 1,
        customization_session=None
    ) -> CartItem:
        if not product.is_in_stock:
            raise ValueError("Produit épuisé.")
            
        if quantity > product.stock_quantity:
            raise ValueError(f"Stock insuffisant. Disponible : {product.stock_quantity}")

        # Les produits personnalisés sont toujours uniques
        if customization_session:
            item = CartItem.objects.create(
                cart=cart,
                product=product,
                customization_session=customization_session,
                quantity=quantity,
                unit_price=product.effective_price + (customization_session.frame_option.extra_price if customization_session.frame_option else 0)
            )
        else:
            # Produit standard
            item, created = CartItem.objects.get_or_create(
                cart=cart,
                product=product,
                customization_session__isnull=True,
                defaults={'unit_price': product.effective_price}
            )
            if not created:
                if item.quantity + quantity > product.stock_quantity:
                    raise ValueError(f"Stock insuffisant pour augmenter la quantité. Disponible : {product.stock_quantity}")
                item.quantity += quantity
                item.save()
            else:
                item.quantity = quantity
                item.save()
        
        return item

    @staticmethod
    def update_quantity(cart_item: CartItem, new_quantity: int) -> CartItem:
        if new_quantity <= 0:
            cart_item.delete()
            return None
            
        if new_quantity > cart_item.product.stock_quantity:
            raise ValueError(f"Stock insuffisant. Disponible : {cart_item.product.stock_quantity}")
            
        cart_item.quantity = new_quantity
        cart_item.save()
        return cart_item

    @staticmethod
    def remove_item(cart_item: CartItem) -> None:
        cart_item.delete()

    @staticmethod
    def clear_cart(cart: Cart) -> None:
        cart.items.all().delete()

    @staticmethod
    def merge_carts(anonymous_cart: Cart, user_cart: Cart) -> Cart:
        with transaction.atomic():
            for anon_item in anonymous_cart.items.all():
                if anon_item.customization_session:
                    # Toujours transférer les personnalisés
                    anon_item.cart = user_cart
                    anon_item.save()
                else:
                    # Fusionner les standards
                    user_item = user_cart.items.filter(
                        product=anon_item.product, 
                        customization_session__isnull=True
                    ).first()
                    if user_item:
                        user_item.quantity += anon_item.quantity
                        user_item.save()
                        anon_item.delete()
                    else:
                        anon_item.cart = user_cart
                        anon_item.save()
            anonymous_cart.delete()
        return user_cart

    @staticmethod
    def track_add_to_cart_behavior(request, product: Product) -> None:
        cart_products = request.session.get('cart_products', [])
        entry = {
            'product_id': product.pk,
            'category_id': product.category_id,
            'timestamp': timezone.now().isoformat(),
        }
        # Limiter aux 10 derniers
        cart_products = [c for c in cart_products if c['product_id'] != product.pk]
        cart_products.append(entry)
        request.session['cart_products'] = cart_products[-10:]
        request.session.modified = True


class OrderService:

    COMMISSION_RATE = Decimal('15.00')

    @staticmethod
    def create_order_from_cart(
        cart: Cart,
        checkout_data: dict,
        user
    ) -> Order:
        if cart.is_empty:
            raise ValueError("Le panier est vide.")
            
        with transaction.atomic():
            # Valider stock
            for item in cart.items.all():
                if item.quantity > item.product.stock_quantity:
                    raise ValueError(f"Stock insuffisant pour {item.product.title}.")

            # Créer commande
            order = Order.objects.create(
                user=user,
                subtotal=cart.subtotal,
                total_amount=cart.subtotal, # + delivery_fee - discount
                delivery_name=checkout_data['delivery_name'],
                delivery_phone=checkout_data['delivery_phone'],
                delivery_address=checkout_data['delivery_address'],
                delivery_city=checkout_data['delivery_city'],
                delivery_notes=checkout_data.get('delivery_notes', ''),
            )

            # Créer items immuables
            OrderService._create_order_items(order, cart)
            
            # Update status des personnalisations
            for item in cart.items.filter(customization_session__isnull=False):
                session = item.customization_session
                session.status = CustomizationSession.SessionStatus.ORDERED
                session.save()
                
            return order

    @staticmethod
    def _create_order_items(order: Order, cart: Cart) -> list[OrderItem]:
        items_to_create = []
        for cart_item in cart.items.select_related('product__artisan'):
            payout = cart_item.line_total * (
                1 - OrderService.COMMISSION_RATE / 100
            )
            items_to_create.append(OrderItem(
                order                 = order,
                product               = cart_item.product,
                customization_session = cart_item.customization_session,
                artisan               = cart_item.product.artisan,
                product_title         = cart_item.product.title,
                unit_price            = cart_item.unit_price,
                quantity              = cart_item.quantity,
                line_total            = cart_item.line_total,
                commission_rate       = OrderService.COMMISSION_RATE,
                artisan_payout        = payout,
            ))
        return OrderItem.objects.bulk_create(items_to_create)

    @staticmethod
    def transition_status(
        order: Order,
        new_status: str,
        changed_by,
        note: str = ''
    ) -> Order:
        ALLOWED_TRANSITIONS = {
            'pending':   ['paid', 'cancelled'],
            'paid':      ['confirmed', 'cancelled', 'refunded'],
            'confirmed': ['in_craft', 'cancelled'],
            'in_craft':  ['shipped'],
            'shipped':   ['delivered'],
        }
        allowed = ALLOWED_TRANSITIONS.get(order.status, [])
        if new_status not in allowed:
            raise ValueError(
                f"Transition {order.status} → {new_status} non autorisée."
            )

        old_status   = order.status
        order.status = new_status
        order.save(update_fields=['status', 'updated_at'])

        OrderStatusHistory.objects.create(
            order      = order,
            old_status = old_status,
            new_status = new_status,
            changed_by = changed_by,
            note       = note,
        )
        return order
