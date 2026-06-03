from django.core.exceptions import ValidationError
from PIL import Image
import os
import re

# Constantes de validation
MAX_UPLOAD_SIZE_MB   = 10
MIN_WIDTH_PX         = 800
MIN_HEIGHT_PX        = 600
ALLOWED_EXTENSIONS   = ['.jpg', '.jpeg', '.png', '.webp']
ALLOWED_MIME_TYPES   = ['image/jpeg', 'image/png', 'image/webp']


def validate_image_extension(file) -> None:
    """Valide que l'extension du fichier est autorisée."""
    ext = os.path.splitext(file.name)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValidationError(
            f"Format non supporté. Formats acceptés : {', '.join(ALLOWED_EXTENSIONS)}"
        )


def validate_image_size(file) -> None:
    """Valide que le fichier ne dépasse pas MAX_UPLOAD_SIZE_MB."""
    if file.size > MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        raise ValidationError(
            f"L'image est trop lourde. Taille maximale : {MAX_UPLOAD_SIZE_MB} Mo."
        )


def validate_image_dimensions(file) -> None:
    """
    Ouvre l'image avec Pillow et valide la résolution minimale.
    Une résolution trop faible donnerait un rendu pixélisé à l'impression.
    """
    try:
        img = Image.open(file)
        width, height = img.size
        if width < MIN_WIDTH_PX or height < MIN_HEIGHT_PX:
            raise ValidationError(
                f"Résolution trop faible ({width}×{height} px). "
                f"Minimum requis : {MIN_WIDTH_PX}×{MIN_HEIGHT_PX} px."
            )
    except Exception as e:
        if isinstance(e, ValidationError):
            raise
        raise ValidationError("Impossible de lire l'image. Vérifiez que le fichier n'est pas corrompu.")
    finally:
        if hasattr(file, 'seek'):
            file.seek(0)  # Réinitialiser le curseur pour la sauvegarde Django


def validate_engraving_text(text: str) -> None:
    """
    Valide le texte gravé :
    - Pas de caractères HTML/script (XSS)
    - Longueur max 200 caractères
    - Pas uniquement des espaces
    """
    if re.search(r'<[^>]+>', text):
        raise ValidationError("Le texte ne peut pas contenir de balises HTML.")
    if len(text.strip()) == 0 and len(text) > 0:
        raise ValidationError("Le texte ne peut pas être composé uniquement d'espaces.")
