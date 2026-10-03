"""Property-based test for audit IP hashing never disclosing the raw IP (Property 16).

Validates: Requirements 9.3.
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from app.repos.audit_log_repo import hash_client_ip

_ip_like_text = st.text(min_size=1, max_size=50)
_salt_text = st.text(min_size=1, max_size=50)


# Feature: aslinumber-p2-tenancy-brands, Property 16: Audit IP hashing
# never discloses the raw IP
@settings(max_examples=100)
@given(salt=_salt_text, ip=_ip_like_text)
def test_hashed_ip_never_equals_the_raw_ip(salt: str, ip: str) -> None:
    """For any client IP address string, the stored ipHash never equals

    the raw IP. (A substring check is deliberately not asserted here: a
    short IP-like string can trivially appear as a substring of a long
    hex digest by chance -- e.g. ip="0" inside a hash containing a "0"
    character -- which is not a disclosure of the IP, just coincidental
    overlap in a hex alphabet. "Never equals" is the actual guarantee
    hash_client_ip makes; recovering the raw IP from the hash is a
    preimage-resistance property of SHA-256 itself, not something a
    string-containment check can usefully test.)
    """
    hashed = hash_client_ip(salt, ip)

    assert hashed != ip


# Feature: aslinumber-p2-tenancy-brands, Property 16: Audit IP hashing
# never discloses the raw IP
@settings(max_examples=100)
@given(salt=_salt_text, ip=_ip_like_text)
def test_hashing_is_deterministic_for_the_same_salt_and_ip(salt: str, ip: str) -> None:
    """Hashing the same (salt, ip) pair twice yields the same result,

    so a repeated lookup by hash remains possible without storing the
    raw IP.
    """
    first = hash_client_ip(salt, ip)
    second = hash_client_ip(salt, ip)

    assert first == second
