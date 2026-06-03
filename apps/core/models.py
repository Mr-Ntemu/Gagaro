from django.db import models

class TimeStampedModel(models.Model):
    """Ajoute created_at et updated_at à tous les modèles enfants."""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
