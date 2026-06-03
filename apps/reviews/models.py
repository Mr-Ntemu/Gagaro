from django.db import models
from django.utils.translation import gettext_lazy as _
from apps.core.models import TimeStampedModel
from PIL import Image
from io import BytesIO
from django.core.files.base import ContentFile
import os
import logging

logger = logging.getLogger(__name__)

from apps.reviews.managers import ReviewManager

class Review(TimeStampedModel):
    """
    Avis client sur un produit commandé et reçu.
    Un client ne peut laisser qu'un seul avis par produit commandé.
    L'avis n'est autorisé que si la commande est DELIVERED.
    """

    class ModerationStatus(models.TextChoices):
        PENDING  = 'pending',  'En attente de modération'
        APPROVED = 'approved', 'Approuvé'
        REJECTED = 'rejected', 'Rejeté'

    objects = ReviewManager()

    # Relations
    user       = models.ForeignKey(
                   'accounts.KadoyaUser',
                   on_delete=models.CASCADE,
                   related_name='reviews'
                 )
    product    = models.ForeignKey(
                   'catalogue.Product',
                   on_delete=models.CASCADE,
                   related_name='reviews'
                 )
    order      = models.ForeignKey(
                   'orders.Order',
                   on_delete=models.CASCADE,
                   related_name='reviews',
                   help_text="Commande qui justifie cet avis (doit être DELIVERED)"
                 )
    order_item = models.ForeignKey(
                   'orders.OrderItem',
                   on_delete=models.CASCADE,
                   related_name='review',
                   null=True, blank=True,
                   help_text="OrderItem spécifique (pour les commandes multi-articles)"
                 )

    # Contenu
    rating     = models.PositiveSmallIntegerField(
                   choices=[(i, f"{i} étoile{'s' if i > 1 else ''}") for i in range(1, 6)],
                   help_text="Note de 1 à 5 étoiles"
                 )
    title      = models.CharField(
                   max_length=150, blank=True,
                   help_text="Titre court de l'avis (optionnel)"
                 )
    body       = models.TextField(
                   help_text="Corps de l'avis (min 10 caractères)"
                 )

    # Modération
    status     = models.CharField(
                   max_length=20,
                   choices=ModerationStatus.choices,
                   default=ModerationStatus.PENDING
                 )
    moderated_by  = models.ForeignKey(
                      'accounts.KadoyaUser',
                      on_delete=models.SET_NULL,
                      null=True, blank=True,
                      related_name='moderated_reviews'
                    )
    moderated_at  = models.DateTimeField(null=True, blank=True)
    rejection_note = models.TextField(
                       blank=True,
                       help_text="Motif de rejet visible par le client"
                     )

    # Réponse artisan
    artisan_reply       = models.TextField(
                            blank=True,
                            help_text="Réponse publique de l'artisan à cet avis"
                          )
    artisan_replied_at  = models.DateTimeField(null=True, blank=True)

    # Utilité
    helpful_count  = models.PositiveIntegerField(
                       default=0,
                       help_text="Nombre de personnes ayant trouvé cet avis utile"
                     )

    class Meta:
        verbose_name        = 'Avis client'
        verbose_name_plural = 'Avis clients'
        ordering            = ['-created_at']
        constraints         = [
            # Un seul avis par client par produit
            models.UniqueConstraint(
                fields=['user', 'product'],
                name='unique_review_per_user_per_product'
            )
        ]
        indexes = [
            models.Index(fields=['product', 'status']),
            models.Index(fields=['user', 'status']),
        ]

    def __str__(self) -> str:
        return (
            f"Avis de {self.user.full_name} sur "
            f"{self.product.title} ({self.rating}★)"
        )

    @property
    def is_approved(self) -> bool:
        return self.status == self.ModerationStatus.APPROVED

    @property
    def has_photos(self) -> bool:
        return self.photos.exists()

    @property
    def star_range(self) -> range:
        """Pour itérer les étoiles dans les templates Django."""
        return range(1, 6)


class ReviewPhoto(TimeStampedModel):
    """
    Photo du produit reçu attachée à un avis.
    Max 3 photos par avis.
    """
    review    = models.ForeignKey(
                  Review,
                  on_delete=models.CASCADE,
                  related_name='photos'
                )
    image     = models.ImageField(
                  upload_to='reviews/photos/%Y/%m/',
                  help_text="Photo du produit reçu par le client"
                )
    thumbnail = models.ImageField(
                  upload_to='reviews/thumbs/%Y/%m/',
                  blank=True, null=True,
                  help_text="Miniature 300×300 générée automatiquement"
                )
    caption   = models.CharField(
                  max_length=200, blank=True,
                  help_text="Légende optionnelle"
                )
    order     = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name        = 'Photo avis'
        verbose_name_plural = 'Photos avis'
        ordering            = ['order', 'id']

    def save(self, *args, **kwargs):
        """Génère automatiquement la miniature via Pillow à la sauvegarde."""
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if self.image and not self.thumbnail:
            self._generate_thumbnail()

    def _generate_thumbnail(self) -> None:
        """
        Crée une miniature 300×300 (crop centré).
        """
        try:
            img = Image.open(self.image.path)
            
            # Conversion en RGB si nécessaire (pour JPEG)
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
                
            img.thumbnail((300, 300), Image.Resampling.LANCZOS)

            # Crop centré carré
            width, height = img.size
            size = min(width, height)
            left   = (width  - size) // 2
            top    = (height - size) // 2
            img    = img.crop((left, top, left + size, top + size))

            buffer = BytesIO()
            img.save(buffer, format='JPEG', quality=85)
            buffer.seek(0)

            filename = os.path.splitext(
                os.path.basename(self.image.name)
            )[0]
            self.thumbnail.save(
                f"thumb_{filename}.jpg",
                ContentFile(buffer.read()),
                save=True
            )
        except Exception as e:
            logger.error(
                f"Erreur génération miniature avis {self.pk} : {e}"
            )
