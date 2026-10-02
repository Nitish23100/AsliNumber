"""Unit tests for backend.app.auth.tokens.

Concrete examples covering access token issuance/decoding and refresh token
generation/hashing. See tests/unit/test_tokens_properties.py (task 5.4) for
the Hypothesis-based property test validating Property 2 (access token
claim round-trip) across arbitrary inputs.
"""

import jwt
import pytest

from app.auth.tokens import (
    decode_access_token,
    generate_refresh_token,
    hash_refresh_token,
    issue_access_token,
)
from app.models.role import Role


@pytest.fixture(autouse=True)
def _jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    # issue_access_token/decode_access_token instantiate Settings()
    # internally (no settings parameter, per the design's exact function
    # signatures), so JWT_SECRET must come from the environment rather
    # than a constructor kwarg. Settings.JWT_SECRET defaults to "" (an
    # invalid HMAC key), so every test in this module needs a non-empty
    # secret set before issuing or decoding a token.
    monkeypatch.setenv("JWT_SECRET", "unit-test-jwt-secret-value-32-bytes-min")


def test_issue_then_decode_round_trips_sub_tid_role() -> None:
    token = issue_access_token(user_id="user-123", tenant_id="tenant-456", role=Role.ADMIN)

    claims = decode_access_token(token)

    assert claims.sub == "user-123"
    assert claims.tid == "tenant-456"
    assert claims.role == Role.ADMIN


def test_decode_access_token_with_tampered_signature_raises() -> None:
    token = issue_access_token(user_id="user-123", tenant_id="tenant-456", role=Role.VIEWER)
    # Flip the last character of the signature segment to corrupt it
    # without otherwise changing the token's structure.
    header, payload, signature = token.split(".")
    tampered_char = "A" if signature[-1] != "A" else "B"
    tampered_signature = signature[:-1] + tampered_char
    tampered_token = f"{header}.{payload}.{tampered_signature}"

    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(tampered_token)


def test_generate_refresh_token_differs_on_each_call() -> None:
    first = generate_refresh_token()
    second = generate_refresh_token()

    assert first != second


def test_hash_refresh_token_is_deterministic_and_never_equals_input() -> None:
    token = generate_refresh_token()

    first_hash = hash_refresh_token(token)
    second_hash = hash_refresh_token(token)

    assert first_hash == second_hash
    assert first_hash != token
