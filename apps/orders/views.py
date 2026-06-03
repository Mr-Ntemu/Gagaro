import json
import logging
from django.shortcuts import render, get_object_or_404, redirect
from django.views import View
from django.views.generic import DetailView
from django.http import JsonResponse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.urls import reverse
from apps.catalogue.models import Product
from apps.customization.models import CustomizationSession
from .models import Cart, CartItem, Order
from .forms import CheckoutForm
from .services import CartService, OrderService

logger = logging.getLogger(__name__)

class CartView(View):
    template_name = 'orders/cart.html'

    def get(self, request):
        cart = CartService.get_or_create_cart(request)
        return render(request, self.template_name, {
            'cart':  cart,
            'items': cart.items.select_related(
                         'product__category',
                         'customization_session'
                     ).order_by('created_at'),
        })


class AddToCartView(View):

    def post(self, request):
        try:
            data       = json.loads(request.body)
            product_id = data.get('product_id')
            quantity   = int(data.get('quantity', 1))
            session_id = data.get('customization_session_id')

            logger.info(f"AddToCart: product_id={product_id}, quantity={quantity}, user={request.user}")

            product = get_object_or_404(Product, pk=product_id, status='active')
            logger.info(f"AddToCart: product found={product.title}, is_in_stock={product.is_in_stock}")

            customization = None
            if session_id:
                customization = get_object_or_404(
                    CustomizationSession,
                    pk=session_id,
                    user=request.user,
                    status='completed'
                )

            cart     = CartService.get_or_create_cart(request)
            CartService.add_item(cart, product, quantity, customization)
            CartService.track_add_to_cart_behavior(request, product)

            return JsonResponse({
                'success':          True,
                'cart_total_items': cart.total_items,
                'message':          f'"{product.title}" ajouté au panier.',
            })

        except ValueError as e:
            logger.warning(f"AddToCart ValueError: {e}")
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
        except Exception as e:
            logger.error(f"AddToCart Exception: {type(e).__name__}: {e}", exc_info=True)
            return JsonResponse({
                'success': False,
                'error':   f'Erreur: {type(e).__name__}: {str(e)}'
            }, status=500)


class UpdateCartItemView(View):

    def post(self, request, item_id: int):
        cart = CartService.get_or_create_cart(request)
        cart_item = get_object_or_404(
            CartItem, pk=item_id, cart=cart
        )
        data         = json.loads(request.body)
        new_quantity = int(data.get('quantity', 1))

        try:
            CartService.update_quantity(cart_item, new_quantity)
            cart = CartService.get_or_create_cart(request)
            return JsonResponse({
                'success':          True,
                'line_total':       str(cart_item.line_total if cart_item else 0),
                'cart_subtotal':    str(cart.subtotal),
                'cart_total_items': cart.total_items,
            })
        except ValueError as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)


class RemoveFromCartView(View):

    def delete(self, request, item_id: int):
        cart = CartService.get_or_create_cart(request)
        cart_item = get_object_or_404(
            CartItem, pk=item_id, cart=cart
        )
        CartService.remove_item(cart_item)
        cart = CartService.get_or_create_cart(request)
        return JsonResponse({
            'success':          True,
            'cart_total_items': cart.total_items,
            'cart_subtotal':    str(cart.subtotal),
            'is_empty':         cart.is_empty,
        })


class CheckoutView(LoginRequiredMixin, View):
    template_name = 'orders/checkout.html'

    def get(self, request):
        cart = CartService.get_or_create_cart(request)
        if cart.is_empty:
            messages.warning(request, "Votre panier est vide.")
            return redirect('orders:cart')

        form = CheckoutForm(initial={
            'delivery_name':  request.user.get_full_name(),
            'delivery_phone': getattr(request.user, 'phone', ''),
        })
        return render(request, self.template_name, {
            'cart': cart,
            'form': form,
            'items': cart.items.select_related('product', 'customization_session'),
        })

    def post(self, request):
        cart = CartService.get_or_create_cart(request)
        if cart.is_empty:
            return redirect('orders:cart')

        form = CheckoutForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {
                'cart': cart,
                'form': form,
                'items': cart.items.select_related('product'),
            })

        try:
            order = OrderService.create_order_from_cart(
                cart          = cart,
                checkout_data = form.cleaned_data,
                user          = request.user,
            )
            return redirect('payments:initiate', reference=order.reference)

        except ValueError as e:
            messages.error(request, str(e))
            return render(request, self.template_name, {
                'cart': cart, 'form': form,
                'items': cart.items.select_related('product'),
            })


class OrderConfirmationView(LoginRequiredMixin, DetailView):
    template_name   = 'orders/confirmation.html'
    context_object_name = 'order'

    def get_queryset(self):
        return Order.objects.for_user(self.request.user).with_items()

    def get_object(self):
        return get_object_or_404(
            self.get_queryset(),
            reference=self.kwargs['reference']
        )
