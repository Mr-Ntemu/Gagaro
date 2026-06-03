import os
import random
import urllib.request
from urllib.error import URLError
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.core.files.base import ContentFile
from django.utils.text import slugify
from apps.accounts.models import KadoyaUser, UserRole
from apps.catalogue.models import Category, Product, ProductImage

class Command(BaseCommand):
    help = 'Génère des catégories et produits de démonstration pour le Sprint 2'

    def handle(self, *args, **options):
        self.stdout.write('Démarrage du peuplement du catalogue...')

        # 1. Récupération des artisans (du seed Sprint 1)
        artisans = KadoyaUser.objects.filter(role=UserRole.ARTISAN)
        if not artisans.exists():
            self.stdout.write(self.style.ERROR("Aucun artisan trouvé. Veuillez d'abord lancer seed_demo."))
            return

        # 2. Création des catégories
        categories_data = [
            ('Cadres Photos', 'cadres', Category.CategoryType.CADRES, 'bi-image'),
            ('Tableaux Décoratifs', 'tableaux', Category.CategoryType.TABLEAUX, 'bi-palette'),
            ('Souvenirs & Cadeaux', 'souvenirs', Category.CategoryType.SOUVENIRS, 'bi-gift'),
        ]
        
        categories = []
        for name, slug, cat_type, icon in categories_data:
            cat, created = Category.objects.get_or_create(
                slug=slug,
                defaults={
                    'name': name,
                    'type': cat_type,
                    'icon': icon,
                    'description': f"Découvrez notre collection de {name.lower()}."
                }
            )
            categories.append(cat)
            if created:
                self.stdout.write(f"Catégorie créée: {name}")

        # 3. Création de 20 produits
        products_titles = [
            "Cadre en chêne massif", "Tableau abstrait 'Horizon'", "Souvenir d'Afrique", 
            "Cadre photo minimaliste", "Peinture sur toile 'Océan'", "Boîte cadeau artisanale",
            "Cadre vintage doré", "Tableau moderne 'City'", "Porte-photo sculpté",
            "Cadre multi-photos", "Toile fleurie 'Printemps'", "Coffret surprise",
            "Cadre flottant", "Peinture 'Nuit étoilée'", "Album photo cuir",
            "Cadre format A4 noir", "Tableau géométrique", "Statuette décorative",
            "Cadre photo bois flotté", "Peinture rupestre moderne"
        ]

        tags_pool = ["artisanat", "décoration", "cadeau", "maison", "fait main", "couleur", "bois", "design"]

        for i, title in enumerate(products_titles):
            artisan = random.choice(artisans)
            category = random.choice(categories)
            base_price = random.randint(5000, 85000)
            
            # Promo sur 30% des produits
            discounted_price = None
            if random.random() < 0.3:
                discounted_price = base_price * Decimal('0.8')

            product = Product.objects.create(
                title=title,
                slug=slugify(f"{title}-{i}"),
                description=f"Ceci est une description détaillée pour le produit {title}. Fabriqué avec passion par {artisan.full_name}.",
                category=category,
                artisan=artisan,
                base_price=base_price,
                discounted_price=discounted_price,
                is_customizable=random.choice([True, False]),
                stock_quantity=random.randint(0, 20),
                status=Product.ProductStatus.ACTIVE,
                dimensions=f"{random.randint(10, 50)}x{random.randint(10, 50)} cm",
                tags=", ".join(random.sample(tags_pool, 3))
            )
            
            # 4. Images du produit
            self.stdout.write(f"Téléchargement d'images pour le produit {i+1}/20: {title}...")
            for j in range(2):
                self._add_product_image(product, i, j)

        self.stdout.write(self.style.SUCCESS('Catalogue peuplé avec succès !'))

    def _add_product_image(self, product, product_idx, image_idx):
        """Télécharge une image de picsum.photos et l'associe au produit."""
        width = 600
        height = random.randint(400, 800) # Hauteurs variées pour le masonry
        url = f"https://picsum.photos/seed/kadoya-p-{product_idx}-{image_idx}/{width}/{height}"
        
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as response:
                content = response.read()
                file_name = f"product_{product.id}_{image_idx}.jpg"
                img_obj = ProductImage(
                    product=product,
                    alt_text=product.title,
                    is_cover=(image_idx == 0),
                    order=image_idx
                )
                img_obj.image.save(file_name, ContentFile(content), save=True)
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"Erreur téléchargement image: {e}"))
