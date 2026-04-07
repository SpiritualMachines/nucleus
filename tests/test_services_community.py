"""Tests for community contact saving and reporting in core/services.py."""

from datetime import datetime, timedelta

from core import services


def test_save_contact_creates_record():
    contact = services.save_community_contact(
        first_name="Alice",
        email="alice@example.com",
        last_name="Smith",
        phone="555-1111",
    )
    assert contact.id is not None
    assert contact.first_name == "Alice"
    assert contact.email == "alice@example.com"


def test_save_contact_optional_fields_default_to_none():
    contact = services.save_community_contact(first_name="Bob", email="bob@test.com")
    assert contact.last_name is None
    assert contact.phone is None
    assert contact.brought_in_by is None
    assert contact.other_reason is None
    assert contact.staff_name is None


def test_save_community_tour_record():
    contact = services.save_community_contact(
        first_name="Community Tour",
        email="",
        is_community_tour=True,
        staff_name="Jane Staff - 2pm walk-in group",
    )
    assert contact.is_community_tour is True
    assert contact.staff_name == "Jane Staff - 2pm walk-in group"


def test_save_contact_stores_brought_in_by():
    contact = services.save_community_contact(
        first_name="Carol",
        email="carol@test.com",
        brought_in_by="3D Printing",
    )
    assert contact.brought_in_by == "3D Printing"


def test_save_contact_stores_other_reason():
    contact = services.save_community_contact(
        first_name="Dave",
        email="dave@test.com",
        other_reason="Interested in laser cutting",
    )
    assert contact.other_reason == "Interested in laser cutting"


def test_save_contact_visited_at_defaults_to_now():
    before = datetime.now()
    contact = services.save_community_contact(first_name="Eve", email="eve@test.com")
    after = datetime.now()
    assert before <= contact.visited_at <= after


def test_save_contact_accepts_explicit_visited_at():
    specific_time = datetime(2026, 1, 15, 10, 30)
    contact = services.save_community_contact(
        first_name="Frank",
        email="frank@test.com",
        visited_at=specific_time,
    )
    assert contact.visited_at == specific_time


# --- Report queries ---


def test_community_contacts_report_returns_in_range_records():
    now = datetime.now()
    services.save_community_contact(
        first_name="In Range", email="inrange@test.com", visited_at=now
    )
    result = services.get_community_contacts_report(
        now - timedelta(hours=1), now + timedelta(hours=1)
    )
    assert len(result["rows"]) == 1
    assert result["rows"][0][1] == "In Range"


def test_community_contacts_report_excludes_out_of_range():
    now = datetime.now()
    services.save_community_contact(
        first_name="Old",
        email="old@test.com",
        visited_at=now - timedelta(days=10),
    )
    result = services.get_community_contacts_report(
        now - timedelta(days=1), now + timedelta(days=1)
    )
    assert len(result["rows"]) == 0


def test_community_contacts_report_includes_staff_name():
    now = datetime.now()
    services.save_community_contact(
        first_name="Community Tour",
        email="",
        is_community_tour=True,
        staff_name="Staff Member - notes",
        visited_at=now,
    )
    result = services.get_community_contacts_report(
        now - timedelta(hours=1), now + timedelta(hours=1)
    )
    # Staff name is the last column
    assert result["rows"][0][-1] == "Staff Member - notes"


def test_community_contacts_report_headers_include_staff_name():
    now = datetime.now()
    result = services.get_community_contacts_report(now, now)
    assert "Staff Name and Description" in result["headers"]


def test_community_contacts_report_empty_range_returns_no_rows():
    now = datetime.now()
    result = services.get_community_contacts_report(
        now - timedelta(days=2), now - timedelta(days=1)
    )
    assert result["rows"] == []
    # Headers are always present even when there is no data
    assert len(result["headers"]) > 0
