"""Inventory item management and product sale recording."""

from datetime import datetime
from typing import Optional

from sqlmodel import Session, select

from core.database import engine
from core.models import InventoryItem, ProductSale

__all__ = [
    "get_all_inventory_items",
    "create_inventory_item",
    "delete_inventory_item",
    "record_product_sales",
    "get_product_sales_report",
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


def record_product_sales(txn_id: int, cart_items: list) -> None:
    """Creates ProductSale records for every inventory item in a completed cart.

    Only processes items whose id is an integer (i.e. sourced from InventoryItem).
    Manual free-text cart entries — which have string ids like 'manual_1' — are
    skipped because they have no inventory_item_id to link against.
    """
    with Session(engine) as session:
        sold_at = datetime.now()
        for item in cart_items:
            try:
                item_id = int(item["id"])
            except (ValueError, TypeError):
                continue
            session.add(
                ProductSale(
                    transaction_id=txn_id,
                    inventory_item_id=item_id,
                    item_name=item["name"],
                    unit_price=item["unit_price"],
                    quantity=item["qty"],
                    sold_at=sold_at,
                )
            )
        session.commit()


def get_product_sales_report(start_date: datetime, end_date: datetime) -> list:
    """Returns individual ProductSale records in the given date range, newest first.

    Each entry is a flat list of strings ready for export:
    [sale_id, date, txn_id, item_name, qty, unit_price, total]
    """
    with Session(engine) as session:
        rows = session.exec(
            select(ProductSale)
            .where(ProductSale.sold_at >= start_date, ProductSale.sold_at <= end_date)
            .order_by(ProductSale.sold_at)
        ).all()
        return [
            [
                str(ps.id),
                ps.sold_at.strftime("%Y-%m-%d %H:%M"),
                str(ps.transaction_id),
                ps.item_name,
                str(
                    int(ps.quantity) if ps.quantity == int(ps.quantity) else ps.quantity
                ),
                f"${ps.unit_price:.2f}",
                f"${ps.unit_price * ps.quantity:.2f}",
            ]
            for ps in rows
        ]
