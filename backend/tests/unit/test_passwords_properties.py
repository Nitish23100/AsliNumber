"""Property-based test for backend.app.auth.passwords.

Exhaustive Hypothesis coverage complementing the concrete examples in
tests/unit/test_passwords.py (task 5.1). See design.md's Correctness
Properties section for the full property statement.
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from app.auth.passwords import hash_password, verify_password

# argon2id hashing is deliberately slow (that's the point of using it for
# passwords), so password strings are bounded to a reasonable length to keep
# the overall test suite's wall-clock time manageable while still exercising
# a wide range of inputs (empty-ish, short, long, unicode, etc.).
_password_text = st.text(min_size=1, max_size=200)


# Feature: aslinumber-p1-foundation, Property 1: Password hash round-trip and non-disclosure
# `deadline=None` disables Hypothesis's per-example timing check: argon2id
# hashing is deliberately slow (memory-hard, by design), which legitimately
# exceeds Hypothesis's default 200ms deadline per example. That slowness is
# the point of argon2id, not a performance bug to flag.
@settings(max_examples=100, deadline=None)
@given(password=_password_text, other=_password_text)
def test_password_hash_round_trip_and_non_disclosure(password: str, other: str) -> None:
    """For any password string: hashing then verifying the same string

    succeeds; the stored hash never equals the original plaintext; and
    verifying any different string against that hash fails.
    """
    hashed = hash_password(password)

    # Non-disclosure: the stored hash never equals the original plaintext.
    assert hashed != password

    # Round-trip: verifying the same plaintext against its own hash succeeds.
    assert verify_password(password, hashed) is True

    # Verifying a different string against that hash fails. `other` is
    # generated independently of `password`, so skip the (vanishingly rare)
    # case where Hypothesis happens to draw two equal strings.
    if other != password:
        assert verify_password(other, hashed) is False
