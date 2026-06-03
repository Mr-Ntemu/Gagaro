from django.apps import AppConfig


class ArtisanConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.artisan'

    def ready(self):
        import apps.artisan.signals  # noqa
