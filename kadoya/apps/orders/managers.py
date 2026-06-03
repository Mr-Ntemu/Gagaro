from django.db import models

class OrderQuerySet(models.QuerySet):

    def for_user(self, user):
        return self.filter(user=user)

    def pending_payment(self):
        return self.filter(status='pending')

    def to_validate(self):
        return self.filter(status='paid')

    def with_items(self):
        return self.prefetch_related(
            'items__product',
            'items__customization_session',
            'items__artisan',
        )


class OrderManager(models.Manager):
    def get_queryset(self) -> OrderQuerySet:
        return OrderQuerySet(self.model, using=self._db)

    def for_user(self, user) -> OrderQuerySet:
        return self.get_queryset().for_user(user)

    def with_items(self) -> OrderQuerySet:
        return self.get_queryset().with_items()
