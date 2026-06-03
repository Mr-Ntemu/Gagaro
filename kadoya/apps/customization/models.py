from django.db import models
from django.utils.translation import gettext_lazy as _
from apps.core.models import TimeStampedModel
from decimal import Decimal

class FrameOption(TimeStampedModel):
    """
    Option de taille et matière de cadre proposée pour un produit personnalisable.
    Chaque produit peut avoir plusieurs FrameOption avec des prix différents.
    """

    class FrameMaterial(models.TextChoices):
        BOIS_CLAIR  = 'bois_clair',  _('Bois clair')
        BOIS_FONCE  = 'bois_fonce',  _('Bois foncé')
        BOIS_NOIR   = 'bois_noir',   _('Bois noir')
        METAL_OR    = 'metal_or',    _('Métal doré')
        METAL_ARG   = 'metal_arg',   _('Métal argenté')
        PLASTIQUE   = 'plastique',   _('Plastique moderne')

    product      = models.ForeignKey(
                     'catalogue.Product',
                     on_delete=models.CASCADE,
                     related_name='frame_options'
                   )
    label        = models.CharField(max_length=100,
                                     help_text=_("Ex: Petit (13x18 cm)"))
    width_cm     = models.DecimalField(max_digits=6, decimal_places=1)
    height_cm    = models.DecimalField(max_digits=6, decimal_places=1)
    material     = models.CharField(max_length=20, choices=FrameMaterial.choices)
    extra_price  = models.DecimalField(
                     max_digits=8, decimal_places=2, default=0,
                     help_text=_("Prix additionnel par rapport au prix de base du produit")
                   )
    is_available = models.BooleanField(default=True)
    order        = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name        = _('Option de cadre')
        verbose_name_plural = _('Options de cadres')
        ordering            = ['order', 'width_cm']

    def __str__(self) -> str:
        return f"{self.label} — {self.get_material_display()} (+{self.extra_price} FCFA)"

    @property
    def dimensions_display(self) -> str:
        return f"{self.width_cm} × {self.height_cm} cm"


class EngravingFont(models.Model):
    """
    Police de caractères disponible pour la gravure/impression du texte.
    Stocke un aperçu visuel pour l'affichage dans l'UI.
    """
    name         = models.CharField(max_length=100)
    css_family   = models.CharField(
                     max_length=200,
                     help_text=_("Famille CSS ou URL Google Fonts")
                   )
    preview_text = models.CharField(
                     max_length=100,
                     default=_("Avec tout mon amour"),
                     help_text=_("Texte affiché en aperçu dans l'UI")
                   )
    is_active    = models.BooleanField(default=True)
    order        = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = _('Police de gravure')
        ordering     = ['order']

    def __str__(self) -> str:
        return self.name


class CustomizationSession(TimeStampedModel):
    """
    Sauvegarde l'état de personnalisation d'un client pour un produit donné.
    Peut être liée au panier (Sprint 4) ou à une commande (Sprint 5).
    Permet de reprendre une personnalisation en cours.
    """

    class SessionStatus(models.TextChoices):
        IN_PROGRESS = 'in_progress', _('En cours')
        COMPLETED   = 'completed',   _('Terminée')
        ABANDONED   = 'abandoned',   _('Abandonnée')
        ORDERED     = 'ordered',     _('Commandée')

    # Relations
    user         = models.ForeignKey(
                     'accounts.KadoyaUser',
                     on_delete=models.CASCADE,
                     related_name='customization_sessions',
                     null=True, blank=True,
                     help_text=_("Null si session invité (non connecté)")
                   )
    product      = models.ForeignKey(
                     'catalogue.Product',
                     on_delete=models.CASCADE,
                     related_name='customization_sessions'
                   )
    frame_option = models.ForeignKey(
                     FrameOption,
                     on_delete=models.SET_NULL,
                     null=True, blank=True
                   )
    font         = models.ForeignKey(
                     EngravingFont,
                     on_delete=models.SET_NULL,
                     null=True, blank=True
                   )

    # Fichiers uploadés
    uploaded_photo      = models.ImageField(
                            upload_to='customizations/photos/%Y/%m/',
                            null=True, blank=True
                          )
    uploaded_photo_thumb = models.ImageField(
                             upload_to='customizations/thumbs/%Y/%m/',
                             null=True, blank=True,
                             help_text=_("Miniature générée automatiquement via Pillow")
                           )

    # Texte gravé
    engraving_text      = models.CharField(max_length=200, blank=True)
    engraving_position  = models.CharField(
                            max_length=20,
                            choices=[
                              ('top',    _('Haut')),
                              ('bottom', _('Bas')),
                              ('left',   _('Gauche')),
                              ('right',  _('Droite')),
                            ],
                            default='bottom'
                          )

    # Métadonnées de session
    session_key  = models.CharField(
                     max_length=40, db_index=True,
                     help_text=_("session.session_key Django (pour invités)")
                   )
    status       = models.CharField(
                     max_length=20,
                     choices=SessionStatus.choices,
                     default=SessionStatus.IN_PROGRESS
                   )
    current_step = models.PositiveSmallIntegerField(
                     default=1,
                     help_text=_("Étape courante du wizard (1=Upload, 2=Cadre, 3=Gravure, 4=Aperçu)")
                   )

    # Prix calculé au moment de la personnalisation
    computed_price = models.DecimalField(
                       max_digits=10, decimal_places=2,
                       null=True, blank=True,
                       help_text=_("Prix final = prix produit + extra_price du cadre")
                     )

    class Meta:
        verbose_name        = _('Session de personnalisation')
        verbose_name_plural = _('Sessions de personnalisation')
        ordering            = ['-created_at']
        indexes             = [
            models.Index(fields=['session_key', 'status']),
            models.Index(fields=['user', 'status']),
        ]

    def __str__(self) -> str:
        return f"Session #{self.pk} — {self.product.title} ({self.get_status_display()})"

    @property
    def is_photo_uploaded(self) -> bool:
        return bool(self.uploaded_photo)

    @property
    def is_frame_selected(self) -> bool:
        return self.frame_option is not None

    @property
    def is_complete(self) -> bool:
        """Une session est complète si photo uploadée + cadre sélectionné."""
        return self.is_photo_uploaded and self.is_frame_selected

    def compute_price(self) -> Decimal:
        """
        Calcule et sauvegarde le prix final.
        Prix = prix effectif du produit + extra_price du cadre sélectionné.
        """
        base_price = self.product.effective_price
        extra = self.frame_option.extra_price if self.frame_option else Decimal('0')
        self.computed_price = base_price + extra
        self.save(update_fields=['computed_price'])
        return self.computed_price
