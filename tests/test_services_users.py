"""Tests for user registration, authentication, and profile management."""

import pytest

from core import services
from core.models import UserRole
from tests.conftest import _make_user

# Minimal valid data for register_user / register_verified_user
_REG_DATA = {
    "email": "newuser@test.com",
    "first_name": "New",
    "last_name": "User",
    "phone": "555-1234",
    "street_address": "10 Maple St",
    "city": "Ottawa",
    "province": "ON",
    "postal_code": "K1A 0A1",
    "emergency_first_name": "Em",
    "emergency_last_name": "Contact",
    "emergency_phone": "555-9000",
}


# --- Registration ---


def test_register_user_creates_account():
    user = services.register_user(_REG_DATA.copy(), "password123")
    assert user.account_number is not None
    assert user.email == "newuser@test.com"


def test_register_user_is_pending_by_default():
    user = services.register_user(_REG_DATA.copy(), "password123")
    assert user.is_active is False


def test_register_user_password_is_hashed():
    user = services.register_user(_REG_DATA.copy(), "password123")
    assert user.password_hash != "password123"


def test_register_user_duplicate_email_raises():
    services.register_user(_REG_DATA.copy(), "password123")
    with pytest.raises(ValueError, match="already registered"):
        services.register_user(_REG_DATA.copy(), "password123")


def test_register_verified_user_is_active_and_id_checked():
    user = services.register_verified_user(_REG_DATA.copy(), "password123")
    assert user.is_active is True
    assert user.id_checked is True


def test_register_verified_user_is_community_role():
    user = services.register_verified_user(_REG_DATA.copy(), "password123")
    role = user.role if isinstance(user.role, str) else user.role.value
    assert role == "community"


# --- Authentication ---


def test_authenticate_user_success(admin_user):
    result = services.authenticate_user("admin@test.com", "testpass123")
    assert result is not None
    assert result.email == "admin@test.com"


def test_authenticate_user_wrong_password_returns_none(admin_user):
    assert services.authenticate_user("admin@test.com", "wrongpassword") is None


def test_authenticate_nonexistent_user_returns_none():
    assert services.authenticate_user("nobody@nowhere.com", "password") is None


# --- Retrieval ---


def test_get_users_returns_all(admin_user, member_user):
    users = services.get_users()
    emails = [u.email for u in users]
    assert "admin@test.com" in emails
    assert "member@test.com" in emails


def test_get_users_filtered_by_role(admin_user, member_user):
    admins = services.get_users(roles=[UserRole.ADMIN])
    assert len(admins) == 1
    role = admins[0].role if isinstance(admins[0].role, str) else admins[0].role.value
    assert role == "admin"


def test_get_user_by_account_returns_correct_user(admin_user):
    fetched = services.get_user_by_account(admin_user.account_number)
    assert fetched is not None
    assert fetched.email == admin_user.email


def test_get_user_by_account_missing_returns_none():
    assert services.get_user_by_account(9999999) is None


def test_search_users_finds_by_first_name(admin_user):
    results = services.search_users("Test")
    assert any(u.email == "admin@test.com" for u in results)


def test_search_users_finds_by_email(admin_user):
    results = services.search_users("admin@test.com")
    assert any(u.email == "admin@test.com" for u in results)


def test_search_users_no_match_returns_empty():
    results = services.search_users("zzznomatch")
    assert results == []


# --- Updates ---


def test_update_user_details_changes_field(admin_user):
    services.update_user_details(admin_user.account_number, {"first_name": "Updated"})
    updated = services.get_user_by_account(admin_user.account_number)
    assert updated.first_name == "Updated"


def test_update_user_password_success(admin_user):
    services.update_user_password(
        admin_user.account_number, "testpass123", "newpass456"
    )
    assert services.authenticate_user("admin@test.com", "newpass456") is not None


def test_update_user_password_rejects_old_password_after_change(admin_user):
    services.update_user_password(
        admin_user.account_number, "testpass123", "newpass456"
    )
    assert services.authenticate_user("admin@test.com", "testpass123") is None


def test_update_user_password_wrong_current_raises(admin_user):
    with pytest.raises(ValueError, match="incorrect"):
        services.update_user_password(
            admin_user.account_number, "wrongcurrent", "newpass"
        )


# --- Approval ---


def test_approve_user_sets_is_active(db_session, admin_user):
    pending = _make_user(99999999999901, "pending@test.com", is_active=False)
    db_session.add(pending)
    db_session.commit()

    services.approve_user(admin_user.account_number, pending.account_number)

    approved = services.get_user_by_account(pending.account_number)
    assert approved.is_active is True
