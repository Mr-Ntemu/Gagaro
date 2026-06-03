import random
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.catalogue.models import Product
from apps.recommendations.models import BehaviorEvent
from apps.recommendations.engine import RecommendationEngine


class Command(BaseCommand):
    help = 'Seed : génère des BehaviorEvents de test pour le moteur de recommandation'

    def add_arguments(self, parser):
        parser.add_argument('--users', type=int, default=5,
                            help='Nombre de clients à traiter (défaut: 5)')
        parser.add_argument('--events', type=int, default=8,
                            help='Événements max par client (défaut: 8)')

    def handle(self, *args, **options):
        User    = get_user_model()
        clients = list(
            User.objects.filter(role='client').order_by('?')[:options['users']]
        )
        products = list(Product.objects.active().order_by('?')[:40])

        if not clients:
            self.stderr.write(self.style.WARNING(
                "Aucun client trouvé. Créez d'abord des utilisateurs avec le rôle 'client'."
            ))
            return

        if not products:
            self.stderr.write(self.style.WARNING("Aucun produit actif trouvé."))
            return

        event_pool = (
            ['view'] * 6 +
            ['cart'] * 3 +
            ['customize'] * 2 +
            ['purchase'] * 1
        )

        created = 0
        for user in clients:
            sample = random.sample(products, min(options['events'], len(products)))
            for product in sample:
                event_type = random.choice(event_pool)
                _, was_created = BehaviorEvent.objects.get_or_create(
                    user       = user,
                    product    = product,
                    event_type = event_type,
                    defaults   = {
                        'category_id':   product.category_id,
                        'tags_snapshot': product.tags or '',
                    }
                )
                if was_created:
                    created += 1

            # Rebuild profile
            try:
                engine = RecommendationEngine(user)
                engine.rebuild_profile()
                self.stdout.write(f"  ✓ Profil reconstruit pour {user.email}")
            except Exception as e:
                self.stderr.write(f"  ✗ Erreur rebuild pour {user.email}: {e}")

        self.stdout.write(self.style.SUCCESS(
            f"\nSeed terminé : {created} événements créés pour {len(clients)} clients."
        ))
