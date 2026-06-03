from django.core.management.base import BaseCommand
from apps.catalogue.models import Product
from apps.customization.models import FrameOption, EngravingFont
from decimal import Decimal

class Command(BaseCommand):
    help = 'Seeds frame options and fonts for customization'

    def handle(self, *args, **options):
        self.stdout.write('Seeding customization data...')

        # 1. Create Engraving Fonts
        fonts_data = [
            {'name': 'Classique Élégant', 'css_family': "'Playfair Display', serif", 'order': 1},
            {'name': 'Moderne Épuré',     'css_family': "'DM Sans', sans-serif",   'order': 2},
            {'name': 'Manuscrit Doux',    'css_family': "'Dancing Script', cursive", 'order': 3},
            {'name': 'Rétro Bold',        'css_family': "'Libre Baskerville', serif", 'order': 4},
        ]

        for fd in fonts_data:
            font, created = EngravingFont.objects.get_or_create(
                name=fd['name'],
                defaults={'css_family': fd['css_family'], 'order': fd['order']}
            )
            if created:
                self.stdout.write(f"Created font: {font.name}")

        # 2. Create Frame Options for customizable products
        customizable_products = Product.objects.filter(is_customizable=True)
        
        if not customizable_products.exists():
            self.stdout.write(self.style.WARNING('No customizable products found. Please mark some products as is_customizable=True first.'))
            # Optional: mark one or two products as customizable for demo if none exist
            # ...
        
        frame_options_templates = [
            {
                'label': 'Petit (13x18 cm)',
                'width_cm': 13,
                'height_cm': 18,
                'material': FrameOption.FrameMaterial.BOIS_CLAIR,
                'extra_price': 0,
                'order': 1
            },
            {
                'label': 'Moyen (20x30 cm)',
                'width_cm': 20,
                'height_cm': 30,
                'material': FrameOption.FrameMaterial.BOIS_FONCE,
                'extra_price': 1500,
                'order': 2
            },
            {
                'label': 'Grand (30x40 cm)',
                'width_cm': 30,
                'height_cm': 40,
                'material': FrameOption.FrameMaterial.METAL_OR,
                'extra_price': 3500,
                'order': 3
            }
        ]

        for product in customizable_products:
            for opt_data in frame_options_templates:
                opt, created = FrameOption.objects.get_or_create(
                    product=product,
                    label=opt_data['label'],
                    defaults={
                        'width_cm': opt_data['width_cm'],
                        'height_cm': opt_data['height_cm'],
                        'material': opt_data['material'],
                        'extra_price': Decimal(str(opt_data['extra_price'])),
                        'order': opt_data['order']
                    }
                )
                if created:
                    self.stdout.write(f"Created option {opt.label} for product {product.title}")

        self.stdout.write(self.style.SUCCESS('Successfully seeded customization data.'))
