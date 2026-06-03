from django.db.models.signals import post_save
from django.dispatch import receiver
from apps.accounts.models import KadoyaUser
from .models import ArtisanProfile


@receiver(post_save, sender=KadoyaUser)
def create_artisan_profile_on_register(sender, instance, created, **kwargs):
    """
    Crée automatiquement un ArtisanProfile à l'inscription
    si l'utilisateur a le rôle 'artisan'.
    """
    if created and instance.is_artisan:
        ArtisanProfile.objects.get_or_create(
            user      = instance,
            defaults  = {
                'shop_name': f"Atelier de {instance.full_name}",
            }
        )
