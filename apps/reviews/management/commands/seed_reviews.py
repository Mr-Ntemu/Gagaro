import random
from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.accounts.models import KadoyaUser
from apps.catalogue.models import Product
from apps.orders.models import Order, OrderItem
from apps.reviews.models import Review, ReviewPhoto
from apps.reviews.services import ReviewService

class Command(BaseCommand):
    help = 'Seed database with demo reviews for delivered orders'

    def handle(self, *args, **options):
        self.stdout.write('Seeding reviews...')
        
        # 1. Get all DELIVERED orders
        delivered_orders = Order.objects.filter(status='delivered')
        
        if not delivered_orders.exists():
            self.stdout.write(self.style.WARNING('No delivered orders found. Please seed orders first.'))
            return

        reviews_created = 0
        
        review_texts = [
            "Le cadre est vraiment beau, ma maman a adoré !",
            "Qualité exceptionnelle, le bois est magnifique. Je recommande vivement.",
            "Livraison un peu longue mais le produit en vaut la peine.",
            "C'est exactement ce que je voulais. Travail très soigné.",
            "Très satisfait de mon achat. L'artisan est très talentueux.",
            "Superbe ! Les finitions sont parfaites.",
            "Un peu plus petit que ce que j'imaginais, mais très joli.",
            "Magnifique pièce, elle trône fièrement dans mon salon.",
            "Top ! Je vais en commander un autre pour offrir.",
            "Rapport qualité/prix imbattable pour du fait main."
        ]

        artisan_replies = [
            "Merci beaucoup pour votre retour ! C'était un plaisir de réaliser cette pièce pour vous.",
            "Ravi que cela vous plaise ! À bientôt sur Kadoya.",
            "Merci pour votre confiance. Nous travaillons à améliorer nos délais de livraison.",
            "Un grand merci pour vos encouragements !",
            "Merci pour votre avis positif. Profitez bien de votre acquisition !"
        ]

        for order in delivered_orders:
            # For each order, create reviews for 1-2 items
            items = list(order.items.all())
            num_reviews = min(len(items), random.randint(1, 2))
            
            selected_items = random.sample(items, num_reviews)
            
            for item in selected_items:
                # Check if review already exists
                if Review.objects.filter(user=order.user, product=item.product).exists():
                    continue
                
                rating = random.randint(3, 5)
                body = random.choice(review_texts)
                
                # Create review
                review = Review.objects.create(
                    user=order.user,
                    product=item.product,
                    order=order,
                    order_item=item,
                    rating=rating,
                    body=body,
                    status=Review.ModerationStatus.APPROVED, # Seed reviews as approved
                    moderated_at=timezone.now()
                )
                
                # 50% chance of photo (placeholder simulation)
                # In a real seed we might download picsum images, 
                # but for now we just create the review.
                
                # 30% chance of artisan reply
                if random.random() < 0.3:
                    review.artisan_reply = random.choice(artisan_replies)
                    review.artisan_replied_at = timezone.now()
                    review.save()
                
                reviews_created += 1

        # 2. Refresh product stats
        self.stdout.write('Refreshing product stats cache...')
        for product in Product.objects.all():
            ReviewService._refresh_product_stats(product)

        self.stdout.write(self.style.SUCCESS(f'Successfully created {reviews_created} reviews.'))
