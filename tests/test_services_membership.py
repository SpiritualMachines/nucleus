"""Tests for memberships and day passes in core/services.py."""

from datetime import datetime

from core import services


def test_add_membership_upgrades_role_to_member(member_user):
    services.add_membership(member_user.account_number, 1)
    updated = services.get_user_by_account(member_user.account_number)
    role = updated.role if isinstance(updated.role, str) else updated.role.value
    assert role == "member"


def test_add_membership_creates_record(member_user):
    services.add_membership(member_user.account_number, 1)
    memberships = services.get_user_memberships(member_user.account_number)
    assert len(memberships) == 1


def test_add_membership_end_date_is_30_days_per_month(member_user):
    services.add_membership(member_user.account_number, 1)
    memberships = services.get_user_memberships(member_user.account_number)
    delta = memberships[0].end_date - memberships[0].start_date
    assert delta.days == 30


def test_add_three_month_membership_spans_90_days(member_user):
    services.add_membership(member_user.account_number, 3)
    memberships = services.get_user_memberships(member_user.account_number)
    delta = memberships[0].end_date - memberships[0].start_date
    assert delta.days == 90


def test_multiple_memberships_stack(member_user):
    services.add_membership(member_user.account_number, 1)
    services.add_membership(member_user.account_number, 1)
    assert len(services.get_user_memberships(member_user.account_number)) == 2


def test_get_user_memberships_empty_by_default(member_user):
    assert services.get_user_memberships(member_user.account_number) == []


def test_add_day_pass_creates_record(member_user):
    services.add_day_pass(member_user.account_number, datetime.now(), "Day Pass")
    passes = services.get_user_day_passes(member_user.account_number)
    assert len(passes) == 1


def test_add_day_pass_stores_description(member_user):
    services.add_day_pass(
        member_user.account_number, datetime.now(), "NBP Library Pass"
    )
    passes = services.get_user_day_passes(member_user.account_number)
    assert passes[0].description == "NBP Library Pass"


def test_get_user_day_passes_empty_by_default(member_user):
    assert services.get_user_day_passes(member_user.account_number) == []


def test_day_passes_do_not_appear_in_memberships(member_user):
    services.add_day_pass(member_user.account_number, datetime.now(), "Day Pass")
    assert services.get_user_memberships(member_user.account_number) == []
