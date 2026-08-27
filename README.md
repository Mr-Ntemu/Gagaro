# Gagaro (Kadoya)

Marketplace e-commerce camerounais mettant en relation **artisans** (cadres photos, tableaux, souvenirs) et **clients**, avec personnalisation de produits et paiement **Mobile Money** (MTN / Orange) via **Monetbil**.

## Stack technique

| Couche | Technologie |
|---|---|
| Backend | Django 6.0.7 |
| Python | 3.12 |
| Base de données | SQLite (dev) / MySQL ou PostgreSQL (prod) |
| Frontend | Bootstrap 5, Bootstrap Icons, Google Fonts |
| Paiement | Monetbil (Mobile Money) |
| Recommandations | PyTorch + scoring comportemental |

## Prérequis

- Python 3.12
- `pip` et `venv`
- Un compte [Monetbil](https://www.monetbil.com) avec une **Service Key** active
- (Optionnel) [ngrok](https://ngrok.com) pour exposer le serveur en local

## Installation

```bash
# 1. Cloner le projet
git clone https://github.com/Mr-Ntemu/Gagaro.git
cd Gagaro

# 2. Créer et activer l'environnement virtuel
python3 -m venv venv
source venv/bin/activate

# 3. Installer les dépendances
pip install -r requirements.txt

# 4. Configurer les variables d'environnement
cp .env.example .env
```

### Configuration du `.env`

Édite le fichier `.env` et renseigne tes clés Monetbil :

```env
SECRET_KEY=django-insecure-your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
DATABASE_URL=sqlite:///db.sqlite3
MEDIA_URL=/media/

# Monetbil (Mobile Money)
MONET_BILL_API_URL=https://api.monetbil.com/payment/v1/
MONET_BILL_PAYOUT_API_URL=https://api.monetbil.com/v1/payouts/
MONET_BILL_SERVICE_KEY=ta_service_key
MONET_BILL_SERVICE_SECRET=ton_service_secret
SITE_URL=http://localhost:8000
```

> **Où trouver mes clés ?** Connecte-toi à ton dashboard Monetbil, section **Applications / Services**. La `SERVICE_KEY` est la clé unique de ton service.

## Lancer le projet

```bash
# 1. Activer l'environnement virtuel
source venv/bin/activate

# 2. Appliquer les migrations
python manage.py migrate

# 3. Lancer le serveur
python manage.py runserver
```

Ouvre ensuite **http://localhost:8000** dans ton navigateur.

## Exposer le serveur en local (port-forwarding)

Pour que **Monetbil puisse te contacter** (notifications de paiement via `notify_url`), ton serveur local doit être accessible depuis internet. Utilise un tunnel :

### Avec ngrok

```bash
# 1. Installer ngrok (https://ngrok.com/download) puis lancer :
ngrok http 8000
```

ngrok affiche une URL publique du type `https://xxxx-xxxx.ngrok-free.app`.

```bash
# 2. Copie cette URL dans le .env (SITE_URL)
SITE_URL=https://xxxx-xxxx.ngrok-free.app

# 3. Redémarre le serveur
python manage.py runserver
```

Le `notify_url` est généré automatiquement à partir de la requête entrante (`request.build_absolute_uri`), donc si tu accèdes au site via l'URL ngrok, Monetbil sera notifié sur cette même URL.

### Alternative : cloudflared

```bash
cloudflared tunnel --url http://localhost:8000
```

Même principe : copie l'URL affichée dans `SITE_URL`.

> **Note :** sans tunnel, le paiement fonctionne quand même grâce au **polling** côté client (`checkPayment`). Le webhook n'est nécessaire que si l'utilisateur ferme la page avant confirmation.

## Déclencher un paiement

1. Crée un compte client (`/auth/register/`)
2. Ajoute des produits au panier depuis le catalogue (`/catalogue/`)
3. Va au panier (`/panier/`) et finalise la commande
4. Tu es redirigé vers `/paiement/initier/<reference>/`
5. Choisis **MTN Mobile Money** ou **Orange Money**, entre ton numéro, clique sur **Payer**
6. Valide la notification push sur ton téléphone

## Structure du projet

```
Gagaro/
├── manage.py
├── config/                 # Configuration Django (settings, urls, wsgi)
├── apps/
│   ├── accounts/           # Utilisateurs & authentification
│   ├── core/               # Modèles de base, page d'accueil
│   ├── catalogue/          # Catalogue produits
│   ├── customization/      # Personnalisation (cadres, gravure)
│   ├── orders/             # Panier & commandes
│   ├── payments/           # Paiement Monetbil
│   ├── artisan/            # Dashboard artisan
│   ├── dashboard/          # Dashboard admin
│   ├── reviews/            # Avis clients
│   └── recommendations/    # Moteur de recommandation ML
├── templates/              # Templates globaux
├── static/                 # Fichiers statiques (CSS, JS)
└── media/                  # Fichiers uploadés
```

## Commandes utiles

```bash
# Créer un superutilisateur (accès admin)
python manage.py createsuperuser

# Vérifier l'état du projet
python manage.py check

# Re-vérifier manuellement des paiements en attente (admin)
# → /kadmin/paiements/ → sélectionner → action "Re-vérifier"
```
