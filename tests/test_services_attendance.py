"""Tests for space sign-in and sign-out logic in core/services.py."""

import pytest

from core import services


def test_sign_in_marks_user_as_signed_in(member_user):
    services.sign_in_user(member_user.account_number, "Workshop")
    assert services.is_user_signed_in(member_user.account_number)


def test_sign_in_without_visit_type_succeeds(member_user):
    services.sign_in_user(member_user.account_number)
    assert services.is_user_signed_in(member_user.account_number)


def test_sign_in_duplicate_raises(member_user):
    services.sign_in_user(member_user.account_number)
    with pytest.raises(ValueError, match="already signed in"):
        services.sign_in_user(member_user.account_number)


def test_sign_out_clears_signed_in_state(member_user):
    services.sign_in_user(member_user.account_number)
    services.sign_out_user(member_user.account_number)
    assert not services.is_user_signed_in(member_user.account_number)


def test_sign_out_when_not_signed_in_raises(member_user):
    with pytest.raises(ValueError, match="not signed in"):
        services.sign_out_user(member_user.account_number)


def test_is_user_signed_in_false_by_default(member_user):
    assert not services.is_user_signed_in(member_user.account_number)


def test_user_can_sign_in_again_after_signing_out(member_user):
    services.sign_in_user(member_user.account_number)
    services.sign_out_user(member_user.account_number)
    # Should not raise
    services.sign_in_user(member_user.account_number)
    assert services.is_user_signed_in(member_user.account_number)


def test_two_users_can_be_signed_in_simultaneously(admin_user, member_user):
    services.sign_in_user(admin_user.account_number)
    services.sign_in_user(member_user.account_number)
    assert services.is_user_signed_in(admin_user.account_number)
    assert services.is_user_signed_in(member_user.account_number)
