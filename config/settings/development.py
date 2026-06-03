from .base import *

DEBUG = True
ALLOWED_HOSTS = ['*']

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# En dev, on n'utilise pas forcement whitenoise pour servir les fichiers statiques de maniere stricte
# mais on le garde dans middleware par simplicite
