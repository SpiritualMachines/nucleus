"""Tests for consumable credit/debit transactions and balance calculations."""

from datetime import datetime

import pytest

from core import services


def test_credit_transaction_increases_balance(member_user):
    services.add_transaction(member_user.account_number, 20.00, "credit", "Top-up")
    assert services.get_user_balance(member_user.account_number) == pytest.approx(20.00)


def test_debit_transaction_decreases_balance(member_user):
    services.add_transaction(member_user.account_number, 20.00, "credit", "Top-up")
    services.add_transaction(member_user.account_number, 5.00, "debit", "3D Print")
    assert services.get_user_balance(member_user.account_number) == pytest.approx(15.00)


def test_balance_is_zero_with_no_transactions(member_user):
    assert services.get_user_balance(member_user.account_number) == pytest.approx(0.00)


def test_balance_can_go_negative(member_user):
    services.add_transaction(member_user.account_number, 5.00, "debit", "Laser time")
    assert services.get_user_balance(member_user.account_number) == pytest.approx(-5.00)


def test_multiple_credits_accumulate(member_user):
    services.add_transaction(member_user.account_number, 10.00, "credit", "Top-up 1")
    services.add_transaction(member_user.account_number, 10.00, "credit", "Top-up 2")
    assert services.get_user_balance(member_user.account_number) == pytest.approx(20.00)


def test_get_user_transactions_returns_credits_and_debits(member_user):
    services.add_transaction(member_user.account_number, 10.00, "credit", "Top-up")
    services.add_transaction(member_user.account_number, 3.00, "debit", "Filament")
    txns = services.get_user_transactions(member_user.account_number)
    assert len(txns) == 2


def test_get_user_transactions_excludes_day_passes(member_user):
    services.add_day_pass(member_user.account_number, datetime.now(), "Day Pass")
    txns = services.get_user_transactions(member_user.account_number)
    assert len(txns) == 0


def test_day_passes_excluded_from_balance(member_user):
    services.add_day_pass(member_user.account_number, datetime.now(), "Day Pass")
    # Day passes store credits=0.0, so balance should remain zero
    assert services.get_user_balance(member_user.account_number) == pytest.approx(0.00)


def test_transactions_for_different_users_are_isolated(admin_user, member_user):
    services.add_transaction(admin_user.account_number, 50.00, "credit", "Admin top-up")
    assert services.get_user_balance(member_user.account_number) == pytest.approx(0.00)
