import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

from django.test import Client
from apps.accounts.models import KadoyaUser

c = Client()

# Créer les users de test si absents
def get_or_create_user(email, password, first_name, last_name, role):
    try:
        return KadoyaUser.objects.get(email=email)
    except KadoyaUser.DoesNotExist:
        if role == 'admin':
            return KadoyaUser.objects.create_superuser(
                email=email, password=password,
                first_name=first_name, last_name=last_name,
                role=role
            )
        return KadoyaUser.objects.create_user(
            email=email, password=password,
            first_name=first_name, last_name=last_name,
            role=role
        )

admin_user   = get_or_create_user('admin@kadoya.com',   'Admin1234!',   'Admin',   'Kadoya', 'admin')
artisan_user = get_or_create_user('artisan1@kadoya.com','Artisan1234!', 'Artisan', 'Test',   'artisan')
client_user  = get_or_create_user('client1@kadoya.com', 'Client1234!',  'Client',  'Test',   'client')

pages = [
    ('Dashboard artisan',   '/artisan/',                  artisan_user),
    ('Profil artisan',      '/artisan/profil/',           artisan_user),
    ('Nouveau produit',     '/artisan/produits/nouveau/', artisan_user),
    ('Mes commandes',       '/commandes/historique/',     client_user),
    ('Profil client',       '/auth/profile/',             client_user),
    ('Admin dashboard',     '/kadmin/',                   admin_user),
]

print("\n=== TEST DES PAGES KADOYA ===\n")
for label, url, user in pages:
    c.force_login(user)
    try:
        response = c.get(url, follow=True)
        status   = response.status_code
        icon     = 'OK ' if status == 200 else 'ERR'
        # Détecter si redirigé vers login
        final_url = response.redirect_chain[-1][0] if response.redirect_chain else url
        redirect_info = f' -> redirigé vers {final_url}' if response.redirect_chain else ''
        print(f'{icon} [{status}] {label}{redirect_info}')
        # Afficher l'erreur template si présente
        if status == 500:
            print(f'     ERREUR 500 sur {url}')
        if hasattr(response, 'context') and response.context:
            ctx = response.context
            if isinstance(ctx, list):
                ctx = ctx[0]
            exc = ctx.get('exception') if hasattr(ctx, 'get') else None
            if exc:
                print(f'     Exception : {exc}')
    except Exception as e:
        print(f'EXC [???] {label} -> {e}')

print("\n=== FIN DU TEST ===\n")