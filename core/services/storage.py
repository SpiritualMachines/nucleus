"""Storage unit and assignment management."""

from datetime import datetime
from typing import Optional

from sqlmodel import Session, desc, select

from core.database import engine
from core.models import StorageAssignment, StorageUnit

__all__ = [
    "get_next_storage_unit_number",
    "create_storage_unit",
    "delete_storage_unit",
    "get_all_storage_units",
    "get_active_storage_assignments",
    "get_archived_storage_assignments",
    "create_storage_assignment",
    "archive_storage_assignment",
    "get_storage_unit_by_id",
    "get_storage_assignment_by_id",
    "update_storage_assignment",
]


def get_next_storage_unit_number() -> str:
    """
    Returns the next available unit number by finding the highest existing
    numeric unit number and incrementing it. Falls back to "1" when no units
    exist or none have a purely numeric label.
    """
    with Session(engine) as session:
        units = session.exec(select(StorageUnit)).all()
        numeric = []
        for u in units:
            try:
                numeric.append(int(u.unit_number))
            except (ValueError, TypeError):
                pass
        return str(max(numeric) + 1) if numeric else "1"


def create_storage_unit(unit_number: str, description: str) -> StorageUnit:
    """Creates and persists a new active storage unit."""
    with Session(engine) as session:
        unit = StorageUnit(
            unit_number=unit_number, description=description, is_active=True
        )
        session.add(unit)
        session.commit()
        session.refresh(unit)
        return unit


def delete_storage_unit(unit_id: int) -> bool:
    """
    Permanently deletes a storage unit. Only permitted when the unit has no
    active (non-archived) assignments. Returns False if active assignments exist.
    """
    with Session(engine) as session:
        active = session.exec(
            select(StorageAssignment).where(
                StorageAssignment.unit_id == unit_id,
                StorageAssignment.archived_at == None,  # noqa: E711
            )
        ).first()
        if active:
            return False
        unit = session.get(StorageUnit, unit_id)
        if unit:
            session.delete(unit)
            session.commit()
        return True


def get_all_storage_units() -> list:
    """Returns all active storage units ordered by unit_number."""
    with Session(engine) as session:
        return session.exec(
            select(StorageUnit)
            .where(StorageUnit.is_active == True)  # noqa: E712
            .order_by(StorageUnit.unit_number)
        ).all()


def get_active_storage_assignments() -> list:
    """
    Returns all non-archived storage assignments joined with their unit.
    Ordered by assigned_at descending (most recent first).
    """
    with Session(engine) as session:
        return session.exec(
            select(StorageAssignment)
            .where(StorageAssignment.archived_at == None)  # noqa: E711
            .order_by(desc(StorageAssignment.assigned_at))
        ).all()


def get_archived_storage_assignments() -> list:
    """Returns all archived storage assignments ordered by archived_at descending."""
    with Session(engine) as session:
        return session.exec(
            select(StorageAssignment)
            .where(StorageAssignment.archived_at != None)  # noqa: E711
            .order_by(desc(StorageAssignment.archived_at))
        ).all()


def create_storage_assignment(
    unit_id: int,
    assigned_to_name: Optional[str],
    user_account_number: Optional[int],
    item_description: Optional[str],
    notes: Optional[str],
    charges_owed: bool,
    charge_type: Optional[str],
    charge_unit_count: Optional[float],
    charge_cost_per_unit: Optional[float],
    charge_notes: Optional[str],
) -> StorageAssignment:
    """
    Creates a new storage assignment linking a unit to an occupant.
    charge_total is computed here from count * cost_per_unit when charges apply.
    """
    charge_total = None
    if charges_owed and charge_unit_count and charge_cost_per_unit:
        charge_total = round(charge_unit_count * charge_cost_per_unit, 2)

    with Session(engine) as session:
        assignment = StorageAssignment(
            unit_id=unit_id,
            assigned_to_name=assigned_to_name,
            user_account_number=user_account_number,
            item_description=item_description,
            notes=notes,
            charges_owed=charges_owed,
            charge_type=charge_type,
            charge_unit_count=charge_unit_count,
            charge_cost_per_unit=charge_cost_per_unit,
            charge_total=charge_total,
            charge_notes=charge_notes,
        )
        session.add(assignment)
        session.commit()
        session.refresh(assignment)
        return assignment


def archive_storage_assignment(assignment_id: int) -> bool:
    """
    Archives a storage assignment by setting archived_at to now.
    Returns False if the assignment does not exist or is already archived.
    """
    with Session(engine) as session:
        assignment = session.get(StorageAssignment, assignment_id)
        if not assignment or assignment.archived_at is not None:
            return False
        assignment.archived_at = datetime.now()
        session.add(assignment)
        session.commit()
        return True


def get_storage_unit_by_id(unit_id: int) -> Optional[StorageUnit]:
    """Returns a single storage unit by primary key, or None."""
    with Session(engine) as session:
        return session.get(StorageUnit, unit_id)


def get_storage_assignment_by_id(assignment_id: int) -> Optional[StorageAssignment]:
    """Returns a single StorageAssignment by primary key, or None if not found."""
    with Session(engine) as session:
        return session.get(StorageAssignment, assignment_id)


def update_storage_assignment(
    assignment_id: int,
    unit_id: int,
    assigned_to_name: Optional[str],
    user_account_number: Optional[int],
    item_description: Optional[str],
    notes: Optional[str],
    charges_owed: bool,
    charge_type: Optional[str],
    charge_unit_count: Optional[float],
    charge_cost_per_unit: Optional[float],
    charge_notes: Optional[str],
) -> Optional[StorageAssignment]:
    """
    Updates all editable fields on an existing StorageAssignment in place.
    charge_total is recomputed from count * cost_per_unit when charges apply,
    preserving the same redundant-storage pattern used in create_storage_assignment.
    assigned_at and archived_at are intentionally excluded — those are lifecycle
    timestamps and must not be editable. Returns None if the assignment does not exist.
    """
    charge_total = None
    if charges_owed and charge_unit_count and charge_cost_per_unit:
        charge_total = round(charge_unit_count * charge_cost_per_unit, 2)

    with Session(engine) as session:
        assignment = session.get(StorageAssignment, assignment_id)
        if not assignment:
            return None
        assignment.unit_id = unit_id
        assignment.assigned_to_name = assigned_to_name
        assignment.user_account_number = user_account_number
        assignment.item_description = item_description
        assignment.notes = notes
        assignment.charges_owed = charges_owed
        assignment.charge_type = charge_type if charges_owed else None
        assignment.charge_unit_count = charge_unit_count if charges_owed else None
        assignment.charge_cost_per_unit = charge_cost_per_unit if charges_owed else None
        assignment.charge_total = charge_total
        assignment.charge_notes = charge_notes if charges_owed else None
        session.add(assignment)
        session.commit()
        session.refresh(assignment)
        return assignment
