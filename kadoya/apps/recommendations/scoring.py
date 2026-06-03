"""
Fonctions de scoring isolées, sans dépendances Django.
Facilitent les tests unitaires et la lisibilité.
"""
import math
from decimal import Decimal
from datetime import datetime, timezone as dt_tz


def temporal_decay(occurred_at: datetime, lambda_: float = 0.1) -> float:
    """
    Facteur de décroissance temporelle exponentielle.
    decay = e^(-λ × jours_depuis_event)
    """
    now  = datetime.now(dt_tz.utc)
    # Ensure occurred_at is aware
    if occurred_at.tzinfo is None:
        occurred_at = occurred_at.replace(tzinfo=dt_tz.utc)
    
    days = (now - occurred_at).days
    return math.exp(-lambda_ * max(0, days))


def compute_event_score(weight: int, occurred_at: datetime) -> float:
    """
    Score d'un événement = poids × décroissance temporelle.
    """
    return weight * temporal_decay(occurred_at)


def compute_category_bonus(
    product_category_id: int,
    client_profile_cats: dict,
    bonus_multiplier: float = 2.0
) -> float:
    """
    Bonus si le produit appartient à une catégorie préférée du client.
    """
    category_score = client_profile_cats.get(str(product_category_id), 0)
    return category_score * bonus_multiplier if category_score > 0 else 0.0


def compute_tag_bonus(
    product_tags: list[str],
    client_tag_profile: dict,
    bonus_per_match: float = 1.5
) -> float:
    """
    Bonus cumulatif pour chaque tag du produit qui correspond
    aux tags préférés du client.
    """
    total = 0.0
    for tag in product_tags:
        tag_score = client_tag_profile.get(tag.strip().lower(), 0)
        if tag_score > 0:
            total += tag_score * bonus_per_match
    return total


def compute_collaborative_bonus(
    product_id: int,
    similar_user_ids: list[int],
    purchase_counts: dict,
    max_bonus: float = 5.0
) -> float:
    """
    Bonus collaboratif : nombre d'utilisateurs similaires
    ayant acheté ce produit.
    """
    count = purchase_counts.get(product_id, 0)
    # Score logarithmique pour éviter la domination des produits populaires
    return min(math.log1p(count) * 1.5, max_bonus)


def compute_price_affinity(
    product_price: Decimal,
    avg_price_viewed: Decimal | None,
    price_tolerance: float = 0.5
) -> float:
    """
    Pénalité si le produit est très éloigné de la fourchette de prix habituelle.
    """
    if not avg_price_viewed or avg_price_viewed == 0:
        return 0.0

    ratio     = float(product_price) / float(avg_price_viewed)
    deviation = abs(ratio - 1.0)

    if deviation <= price_tolerance:
        return 0.0  # Dans la fourchette → pas de pénalité
    else:
        # Pénalité progressive
        return -(deviation - price_tolerance) * 2.0


def normalize_scores(scores: dict) -> dict:
    """
    Normalise un dict {product_id: score} entre 0 et 1.
    """
    if not scores:
        return {}

    max_score = max(scores.values())
    min_score = min(scores.values())
    range_    = max_score - min_score

    if range_ == 0:
        return {pk: 1.0 for pk in scores}

    return {
        pk: (score - min_score) / range_
        for pk, score in scores.items()
    }
