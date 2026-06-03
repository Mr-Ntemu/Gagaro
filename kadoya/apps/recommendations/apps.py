from django.apps import AppConfig

class RecommendationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.recommendations'
    verbose_name = 'Recommandations'

    def ready(self):
        import apps.recommendations.signals  # noqa
