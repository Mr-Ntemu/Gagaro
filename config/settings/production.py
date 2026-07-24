from .base import *
import dj_database_url

DEBUG = False

ALLOWED_HOSTS = ['gagaro.pythonanywhere.com']

DATABASES = {
    'default': dj_database_url.config(
        default=config('DATABASE_URL')
    )
}

# Securite supplementaire
SECURE_SSL_REDIRECT = config('SECURE_SSL_REDIRECT', default=True, cast=bool)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
