from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.catalogue.models import Product
from apps.orders.models import Cart, CartItem, Order, OrderItem
from apps.orders.services import CartService, OrderService
from decimal import Decimal

User = get_user_model()

class Command(BaseCommand):
    help = 'Seeds orders and carts for demo users'

    def handle(self, *args, **options):
        self.stdout.write('Seeding orders data...')

        # 1. Get demo users (Sprint 1)
        # Clients : client@kadoya.com
        demo_client = User.objects.filter(email='client@kadoya.com').first()
        if not demo_client:
            # Create a demo client if not exists
            demo_client = User.objects.create_user(
                email='client@kadoya.com',
                password='password123',
                first_name='Jean-Paul',
                last_name='Fotso',
                role='customer'
            )
            demo_client.phone = '+237691234567'
            demo_client.save()

        # 2. Get some products
        products = Product.objects.filter(status='active')[:5]
        if not products.exists():
            self.stdout.write(self.style.WARNING('No active products found. Please seed products first.'))
            return

        # 3. Create a cart for the demo client
        cart, _ = Cart.objects.get_or_create(user=demo_client)
        cart.items.all().delete()
        
        for product in products[:2]:
            CartService.add_item(cart, product, quantity=1)
        
        self.stdout.write(f"Created cart for {demo_client.email}")

        # 4. Create a PENDING order
        checkout_data = {
            'delivery_name': f"{demo_client.first_name} {demo_client.last_name}",
            'delivery_phone': '+237691234567',
            'delivery_address': 'Quartier Tsinga, Rue des Bougainvilliers',
            'delivery_city': 'Yaoundé',
            'delivery_notes': 'Sonner au portail noir.'
        }
        
        # Create a separate cart for order to avoid clearing the current cart (OrderService doesn't clear it yet as per Sprint 4)
        order_cart = Cart.objects.create(session_key='temp_seed_session')
        for product in products[2:4]:
            CartService.add_item(order_cart, product, quantity=1)
            
        order = OrderService.create_order_from_cart(order_cart, checkout_data, demo_client)
        order_cart.delete()
        
        self.stdout.write(f"Created PENDING order {order.reference}")

        # 5. Create a DELIVERED order
        old_cart = Cart.objects.create(session_key='old_seed_session')
        CartService.add_item(old_cart, products[4], quantity=2)
        
        old_order = OrderService.create_order_from_cart(old_cart, checkout_data, demo_client)
        old_order.status = Order.OrderStatus.DELIVERED
        old_order.save()
        old_cart.delete()

        self.stdout.write(f"Created DELIVERED order {old_order.reference}")
        self.stdout.write(self.style.SUCCESS('Successfully seeded orders data.'))
