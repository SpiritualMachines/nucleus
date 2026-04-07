"""Tests for core/security.py — password hashing and verification."""

from core.security import get_password_hash, verify_password


def test_hash_is_not_plaintext():
    assert get_password_hash("mypassword") != "mypassword"


def test_correct_password_verifies():
    hashed = get_password_hash("mypassword")
    assert verify_password("mypassword", hashed)


def test_wrong_password_fails_verification():
    hashed = get_password_hash("mypassword")
    assert not verify_password("wrongpassword", hashed)


def test_two_hashes_of_same_password_are_different():
    # bcrypt/pbkdf2 uses a salt so repeated hashes must differ
    h1 = get_password_hash("same")
    h2 = get_password_hash("same")
    assert h1 != h2


def test_different_passwords_produce_different_hashes():
    assert get_password_hash("password1") != get_password_hash("password2")


def test_empty_password_hashes_and_verifies():
    hashed = get_password_hash("")
    assert verify_password("", hashed)
    assert not verify_password("notempty", hashed)


def test_long_password_hashes_and_verifies():
    long_pw = "x" * 200
    hashed = get_password_hash(long_pw)
    assert verify_password(long_pw, hashed)
