"""Unit tests for backend.app.auth.passwords.

Concrete examples covering hashing and verification. See
tests/unit/test_passwords_properties.py (task 5.2) for the Hypothesis-based
property test validating Property 1 (password hash round-trip and
non-disclosure) across arbitrary inputs.
"""

from app.auth.passwords import hash_password, verify_password


def test_hash_password_returns_string_different_from_input() -> None:
    plaintext = "correct-horse-battery-staple"

    hashed = hash_password(plaintext)

    assert isinstance(hashed, str)
    assert hashed != plaintext


def test_verify_password_succeeds_for_correct_password() -> None:
    plaintext = "correct-horse-battery-staple"
    hashed = hash_password(plaintext)

    assert verify_password(plaintext, hashed) is True


def test_verify_password_fails_for_incorrect_password() -> None:
    hashed = hash_password("correct-horse-battery-staple")

    assert verify_password("wrong-password", hashed) is False


def test_hash_password_is_salted_differently_each_call() -> None:
    plaintext = "correct-horse-battery-staple"

    first_hash = hash_password(plaintext)
    second_hash = hash_password(plaintext)

    assert first_hash != second_hash
    # Both independently-salted hashes must still verify the same plaintext.
    assert verify_password(plaintext, first_hash) is True
    assert verify_password(plaintext, second_hash) is True


def test_hash_password_uses_argon2id_variant() -> None:
    # The stored hash string should self-identify as argon2id, per
    # Requirement 6.1 and the design's choice of pwdlib's recommended hasher.
    hashed = hash_password("correct-horse-battery-staple")

    assert hashed.startswith("$argon2id$")
