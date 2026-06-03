from django.db import models

class ReviewQuerySet(models.QuerySet):

    def approved(self):
        """Avis validés par la modération."""
        return self.filter(status='approved')

    def for_product(self, product):
        """Avis approuvés pour un produit donné."""
        return self.approved().filter(product=product)

    def with_photos(self):
        """Avis ayant au moins une photo."""
        return self.filter(photos__isnull=False).distinct()

    def by_rating(self, rating: int):
        """Filtrer par note exacte."""
        return self.filter(rating=rating)

    def with_relations(self):
        """Précharge toutes les relations pour éviter N+1."""
        return self.select_related(
            'user', 'product', 'order', 'moderated_by'
        ).prefetch_related('photos')


class ReviewManager(models.Manager):
    def get_queryset(self) -> ReviewQuerySet:
        return ReviewQuerySet(self.model, using=self._db)

    def approved(self) -> ReviewQuerySet:
        return self.get_queryset().approved()

    def for_product(self, product) -> ReviewQuerySet:
        return self.get_queryset().for_product(product)
