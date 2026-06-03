from django.core.exceptions import ValidationError
import os
import re

REVIEW_PHOTO_MAX_MB        = 8
REVIEW_PHOTO_ALLOWED_EXTS  = ['.jpg', '.jpeg', '.png', '.webp']
REVIEW_PHOTO_MIN_DIMENSION = 400   # px minimum


def validate_review_photo_extension(file) -> None:
    ext = os.path.splitext(file.name)[1].lower()
    if ext not in REVIEW_PHOTO_ALLOWED_EXTS:
        raise ValidationError(
            f"Format non supporté. Formats acceptés : "
            f"{', '.join(REVIEW_PHOTO_ALLOWED_EXTS)}"
        )


def validate_review_photo_size(file) -> None:
    if file.size > REVIEW_PHOTO_MAX_MB * 1024 * 1024:
        raise ValidationError(
            f"Photo trop lourde. Maximum {REVIEW_PHOTO_MAX_MB} Mo."
        )


def validate_review_body(text: str) -> None:
    """Valide le corps de l'avis : longueur minimale + pas de spam."""
    if len(text.strip()) < 10:
        raise ValidationError(
            "L'avis doit contenir au moins 10 caractères."
        )
    # Détecter les patterns de spam évidents (répétition excessive)
    if re.search(r'(.)\1{9,}', text):
        raise ValidationError(
            "Votre avis contient des caractères répétitifs suspects."
        )
    # Pas de liens HTTP dans les avis
    if re.search(r'https?://', text, re.IGNORECASE):
        raise ValidationError(
            "Les liens ne sont pas autorisés dans les avis."
        )
