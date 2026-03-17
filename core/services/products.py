"""Product tier CRUD for membership and day pass templates."""

from typing import List, Optional

from sqlmodel import Session, select

from core.database import engine
from core.models import ProductTier

__all__ = [
    "get_product_tiers",
    "get_product_tier",
    "save_product_tier",
    "delete_product_tier",
]


def get_product_tiers(tier_type: str) -> List["ProductTier"]:
    """
    Returns all active ProductTier records for the given type.
    tier_type must be 'membership' or 'daypass'.
    """
    with Session(engine) as session:
        stmt = (
            select(ProductTier)
            .where(ProductTier.tier_type == tier_type)
            .where(ProductTier.is_active == True)  # noqa: E712
            .order_by(ProductTier.name)
        )
        return session.exec(stmt).all()


def get_product_tier(tier_id: int) -> Optional["ProductTier"]:
    """Returns a single ProductTier by ID, or None if not found."""
    with Session(engine) as session:
        return session.get(ProductTier, tier_id)


def save_product_tier(
    name: str,
    tier_type: str,
    price: float,
    duration_days: Optional[int],
    consumables_credits: Optional[float],
    description: Optional[str],
) -> "ProductTier":
    """
    Creates and persists a new ProductTier template.
    Callers are responsible for passing validated values — price must be >= 0,
    and tier_type must be 'membership' or 'daypass'.
    """
    with Session(engine) as session:
        tier = ProductTier(
            name=name,
            tier_type=tier_type,
            price=price,
            duration_days=duration_days,
            consumables_credits=consumables_credits,
            description=description,
            is_active=True,
        )
        session.add(tier)
        session.commit()
        session.refresh(tier)
        return tier


def delete_product_tier(tier_id: int) -> bool:
    """
    Hard-deletes a ProductTier by ID.
    Returns True if the record was found and deleted, False if not found.
    """
    with Session(engine) as session:
        tier = session.get(ProductTier, tier_id)
        if not tier:
            return False
        session.delete(tier)
        session.commit()
        return True
