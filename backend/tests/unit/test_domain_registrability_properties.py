"""Property-based test for domain registrability gating official domains (Property 3).

Validates: Requirements 2.5.
"""

import tldextract
from hypothesis import given, settings
from hypothesis import strategies as st

from app.core.errors import AppError, ErrorCode
from app.services.brand_service import _RFC_2606_RESERVED_TLDS, validate_registrable_domain

_tld_extractor = tldextract.TLDExtract(suffix_list_urls=())

# A mix of plausible registrable domains and near-miss / non-domain
# strings, so generated examples actually exercise the registrability
# boundary rather than almost-always producing an obviously-invalid
# string.
_domain_label = st.text(
    alphabet=st.characters(whitelist_categories=("Ll", "Nd"), max_codepoint=122),
    min_size=1,
    max_size=10,
)
_plausible_domain = st.builds(
    lambda a, b: f"{a}.{b}", _domain_label, st.sampled_from(["com", "test", "co.uk", "org"])
)
_near_miss_candidate = st.one_of(
    st.text(min_size=0, max_size=30),
    st.just(""),
    st.just("localhost"),
    st.just("not a domain"),
    st.just("justaword"),
    _plausible_domain,
)


def _reference_registered_domain(candidate: str) -> str:
    """An independent re-derivation of what validate_registrable_domain should return.

    Mirrors the production function's two-step resolution (real public
    suffix list, then the RFC 2606 reserved-TLD special case) without
    calling the function under test, so the property actually checks the
    function's behavior against a reference computation rather than
    against itself.
    """
    extracted = _tld_extractor(candidate)
    registered_domain = extracted.top_domain_under_public_suffix

    if (
        not registered_domain
        and extracted.subdomain
        and extracted.domain.lower() in _RFC_2606_RESERVED_TLDS
    ):
        last_label = extracted.subdomain.rsplit(".", 1)[-1]
        registered_domain = f"{last_label}.{extracted.domain}"

    return registered_domain


# Feature: aslinumber-p2-tenancy-brands, Property 3: Domain registrability
# gates official domains
@settings(max_examples=100)
@given(candidate=_near_miss_candidate)
def test_domain_registrability_matches_reference_resolution(candidate: str) -> None:
    """A candidate domain is accepted if and only if it resolves to a

    non-empty registered domain (real public suffix, or an RFC 2606
    reserved pseudo-TLD); every string that does not is rejected with
    HTTP 422.
    """
    expected = _reference_registered_domain(candidate)

    if expected:
        result = validate_registrable_domain(candidate)
        assert result == expected
    else:
        try:
            validate_registrable_domain(candidate)
            raised = False
        except AppError as exc:
            raised = True
            assert exc.code == ErrorCode.VALIDATION_ERROR
            assert exc.status_code == 422
        assert raised
