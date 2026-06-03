from django.core.management.base import BaseCommand
from apps.accounts.models import KadoyaUser, UserRole

class Command(BaseCommand):
    help = 'Génère des données de démonstration pour le Sprint 1'

    def handle(self, *args, **options):
        self.stdout.write('Génération des utilisateurs de démo...')

        # 1. Superuser Admin
        admin_email = 'admin@kadoya.com'
        if not KadoyaUser.objects.filter(email=admin_email).exists():
            KadoyaUser.objects.create_superuser(
                email=admin_email,
                password='Admin1234!',
                first_name='Admin',
                last_name='Kadoya'
            )
            self.stdout.write(self.style.SUCCESS(f'Admin créé: {admin_email} / Admin1234!'))

        # 2. Clients
        clients = [
            ('jean.dupont@email.com', 'Jean', 'Dupont'),
            ('marie.curie@email.com', 'Marie', 'Curie'),
        ]
        for email, first, last in clients:
            if not KadoyaUser.objects.filter(email=email).exists():
                KadoyaUser.objects.create_user(
                    email=email,
                    password='Password123!',
                    first_name=first,
                    last_name=last,
                    role=UserRole.CLIENT
                )
                self.stdout.write(f'Client créé: {email}')

        # 3. Artisans
        artisans = [
            ('atelier.bois@email.com', 'Marc', 'Ebéniste'),
            ('pinceau.or@email.com', 'Sophie', 'Peintre'),
        ]
        for email, first, last in artisans:
            if not KadoyaUser.objects.filter(email=email).exists():
                KadoyaUser.objects.create_user(
                    email=email,
                    password='Password123!',
                    first_name=first,
                    last_name=last,
                    role=UserRole.ARTISAN
                )
                self.stdout.write(f'Artisan créé: {email}')

        self.stdout.write(self.style.SUCCESS('Peuplement terminé avec succès !'))
