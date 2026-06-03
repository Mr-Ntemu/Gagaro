"""
Seed : génère des BehaviorEvents de test pour le moteur de recommandation.
Usage : python manage.py shell < apps/recommendations/seed_behaviors.py
        ou directement depuis Django shell.
"""

import random
from django.contrib.auth import get_user_model
from apps.catalogue.models import Product
from apps.recommendations.models import BehaviorEvent
from apps.recommendations.engine import RecommendationEngine

User = get_user_model()

def seed(n_users=5, n_events_per_user=20):
    clients  = list(User.objects.filter(role='client').order_by('?')[:n_users])
    products = list(Product.objects.active().order_by('?')[:40])

    if not clients:
        print("⚠ Aucun client trouvé. Créez d'abord des utilisateurs avec le rôle 'client'.")
        return
    if not products:
        print("⚠ Aucun produit actif trouvé.")
        return

    event_weights = {
        'view':      6,
        'cart':      3,
        'customize': 2,
        'purchase':  1,
    }

    created = 0
    for user in clients:
        # Simuler un profil d'intérêts cohérent
        preferred_products = random.sample(products, min(8, len(products)))
        for product in preferred_products:
            # Choisir un type d'événement pondéré
            event_types = []
            for etype, weight in event_weights.items():
                event_types.extend([etype] * weight)
            event_type = random.choice(event_types)

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

        # Reconstruire le profil du client
        try:
            engine = RecommendationEngine(user)
            engine.rebuild_profile()
            print(f"  ✓ Profil reconstruit pour {user.email}")
        except Exception as e:
            print(f"  ✗ Erreur rebuild pour {user.email}: {e}")

    print(f"\n✅ Seed terminé : {created} événements créés pour {len(clients)} clients.")

seed()
