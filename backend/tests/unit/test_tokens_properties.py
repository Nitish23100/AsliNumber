"""Property-based tests for backend.app.auth.tokens.

Exhaustive Hypothesis coverage complementing the concrete examples in
tests/unit/test_tokens.py (task 5.3). See design.md's Correctness
Properties section for the full statement of Property 2.

Note on scope: Property 2 also mentions "a TenantContext built from that
token SHALL expose the same tid." `TenantContext` does not exist yet (it is
implemented in task 7.1, after this task), so that clause is intentionally
not covered here. These tests exercise only the parts of Property 2 that
`issue_access_token`/`decode_access_token` (task 5.3) implement: the
sub/tid/role claim round-trip, jti uniqueness, the exact 15-minute exp/iat
gap, and rejection of an already-expired token. The TenantContext-specific
clause should be picked up by task 7.2 (role ordering property test) or a
future task once TenantContext exists.
"""

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.auth.tokens import decode_access_token, issue_access_token
from app.config import Settings
from app.models.role import Role

# Non-empty text for user/tenant ids. jwt.encode's default JSON encoder
# serializes str payload values as UTF-8 JSON strings, so this covers
# arbitrary unicode text within a reasonable length bound.
_id_text = st.text(min_size=1, max_size=100)
_role = st.sampled_from(list(Role))


@pytest.fixture(autouse=True)
def _jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    # Same rationale as test_tokens.py: issue_access_token/decode_access_token
    # instantiate Settings() internally, so JWT_SECRET must come from the
    # environment. Settings.JWT_SECRET defaults to "" otherwise.
    monkeypatch.setenv("JWT_SECRET", "unit-test-jwt-secret-value-32-bytes-min")


# Feature: aslinumber-p1-foundation, Property 2: Access token claim round-trip
@settings(max_examples=100)
@given(user_id=_id_text, tenant_id=_id_text, role=_role)
def test_issue_then_decode_round_trips_claims_and_exact_ttl(
    user_id: str, tenant_id: str, role: Role
) -> None:
    """For any valid (userId, tenantId, role) triple, issuing an

    Access_Token and then decoding it SHALL yield the same sub, tid, and
    role values, and an exp claim exactly 15 minutes after iat.
    """
    token = issue_access_token(user_id=user_id, tenant_id=tenant_id, role=role)

    claims = decode_access_token(token)

    assert claims.sub == user_id
    assert claims.tid == tenant_id
    assert claims.role == role
    assert claims.exp - claims.iat == timedelta(minutes=15)


# Feature: aslinumber-p1-foundation, Property 2: Access token claim round-trip
@settings(max_examples=100)
@given(
    triples=st.lists(
        st.tuples(_id_text, _id_text, _role),
        min_size=2,
        max_size=20,
    )
)
def test_issued_tokens_have_unique_jti_across_calls(
    triples: list[tuple[str, str, Role]],
) -> None:
    """A jti SHALL be unique from any previously issued token.

    Issues one Access_Token per generated (userId, tenantId, role) triple
    and confirms every decoded jti across the batch is distinct.
    """
    jtis = [
        decode_access_token(
            issue_access_token(user_id=user_id, tenant_id=tenant_id, role=role)
        ).jti
        for user_id, tenant_id, role in triples
    ]

    assert len(jtis) == len(set(jtis))


# Feature: aslinumber-p1-foundation, Property 2: Access token claim round-trip
@settings(max_examples=100)
@given(user_id=_id_text, tenant_id=_id_text, role=_role)
def test_decode_rejects_expired_token_regardless_of_other_claims(
    user_id: str, tenant_id: str, role: Role
) -> None:
    """Decoding a token whose exp has already passed SHALL be rejected

    regardless of the validity of its other claims. Constructs an
    already-expired JWT directly with pyjwt.encode, using the same secret
    and algorithm as issue_access_token, rather than issuing a token and
    waiting 15 minutes (or mocking time) for it to expire.
    """
    settings_obj = Settings()
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "tid": tenant_id,
        "role": role.value,
        "jti": "11111111-1111-1111-1111-111111111111",
        "iat": now - timedelta(minutes=20),
        "exp": now - timedelta(minutes=5),
    }
    expired_token = jwt.encode(payload, settings_obj.JWT_SECRET, algorithm="HS256")

    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(expired_token)
