"""Tests for bcrypt password verification."""

from app.services.password_util import hash_password, is_bcrypt_hash, verify_password


def test_is_bcrypt_hash():
    h = hash_password("secret")
    assert is_bcrypt_hash(h)
    assert not is_bcrypt_hash("plain-text")


def test_verify_bcrypt_password():
    h = hash_password("my-pass")
    assert verify_password("my-pass", h)
    assert not verify_password("wrong", h)


def test_verify_plaintext_fallback():
    assert verify_password("legacy", "legacy")
    assert not verify_password("nope", "legacy")
