"""Inventory item management."""

from typing import Optional

from sqlmodel import Session, select

from core.database import engine
from core.models import InventoryItem

__all__ = [
    "get_all_inventory_items",
    "create_inventory_item",
    "delete_inventory_item",
]


def get_all_inventory_items() -> list:
    """Returns all active inventory items ordered alphabetically by name."""
    with Session(engine) as session:
        return session.exec(
            select(InventoryItem)
            .where(InventoryItem.is_active == True)  # noqa: E712
            .order_by(InventoryItem.name)
        ).all()


def create_inventory_item(
    name: str, description: Optional[str], price: float
) -> InventoryItem:
    """Creates and persists a new active inventory item."""
    with Session(engine) as session:
        item = InventoryItem(
            name=name, description=description, price=price, is_active=True
        )
        session.add(item)
        session.commit()
        session.refresh(item)
        return item


def delete_inventory_item(item_id: int) -> None:
    """Permanently removes an inventory item by primary key."""
    with Session(engine) as session:
        item = session.get(InventoryItem, item_id)
        if item:
            session.delete(item)
            session.commit()
