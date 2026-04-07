"""
Shared fixtures for the Nucleus test suite.

Every test gets a fresh in-memory SQLite database so tests are fully isolated
and never touch the real hackspace.db file. The core.database.engine reference
is patched automatically for every test via the autouse fixture below, which
ensures all service sub-modules use the in-memory engine.
"""

import pytest
from unittest.mock import patch

from sqlmodel import SQLModel, Session, create_engine

from core.models import User, UserRole
from core.security import get_password_hash


@pytest.fixture()
def test_engine():
    """
    Creates a fresh in-memory SQLite engine with all tables for each test.
    Dropped completely after the test finishes to guarantee isolation.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(engine)
    yield engine
    SQLModel.metadata.drop_all(engine)


@pytest.fixture(autouse=True)
def patch_services_engine(test_engine):
    """
    Automatically redirects every service function to the in-memory engine.
    Patches core.database.engine so all sub-modules that import from it pick
    up the test engine. Each sub-module is also patched directly because
    Python caches the binding at import time.
    """
    sub_modules = [
        "core.services.settings",
        "core.services.preferences",
        "core.services.users",
        "core.services.auth",
        "core.services.attendance",
        "core.services.membership",
        "core.services.transactions",
        "core.services.feedback",
        "core.services.community",
        "core.services.products",
        "core.services.admin",
        "core.services.reporting",
        "core.services.storage",
        "core.services.inventory",
        "core.services.day_pass",
    ]
    patches = [patch("core.database.engine", test_engine)]
    patches.extend(patch(f"{mod}.engine", test_engine) for mod in sub_modules)
    for p in patches:
        p.start()
    yield
    for p in reversed(patches):
        p.stop()


@pytest.fixture()
def db_session(test_engine):
    """Direct database session for test setup and low-level assertions."""
    with Session(test_engine) as session:
        yield session


def _make_user(
    account_number: int,
    email: str,
    role: UserRole = UserRole.COMMUNITY,
    is_active: bool = True,
    first_name: str = "Test",
    last_name: str = "User",
    password: str = "testpass123",
) -> User:
    """Builds a minimally valid User instance for insertion in tests."""
    return User(
        account_number=account_number,
        email=email,
        password_hash=get_password_hash(password),
        role=role,
        is_active=is_active,
        first_name=first_name,
        last_name=last_name,
        phone="555-0100",
        street_address="1 Test St",
        city="Testville",
        province="ON",
        postal_code="A1A 1A1",
        emergency_first_name="Emergency",
        emergency_last_name="Contact",
        emergency_phone="555-9999",
    )


@pytest.fixture()
def admin_user(db_session):
    """Pre-inserted active admin user available to any test that requests it."""
    user = _make_user(10000000000001, "admin@test.com", role=UserRole.ADMIN)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def member_user(db_session):
    """Pre-inserted active member user available to any test that requests it."""
    user = _make_user(10000000000002, "member@test.com", role=UserRole.MEMBER)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user
