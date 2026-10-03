"""Property-based test for official-contact creation defaults and the Authority_Rule (Property 7).

Validates: Requirements 4.2, 4.3, 4.4, 4.5, 4.6.
"""

from datetime import UTC, datetime

from bson import ObjectId
from hypothesis import given, settings
from hypothesis import strategies as st

from app.core.errors import AppError, ErrorCode
from app.models.brand import Alias, Authority, Brand, ContactMethod, ContactStatus, OfficialDomain
from app.models.official_contact import ContactSource
from app.services.brand_service import prepare_official_contact_create, resolve_authority


def _make_brand(official_domains: list[str]) -> Brand:
    return Brand(
        tenantId=ObjectId(),
        slug="examplekart",
        displayName="ExampleKart",
        category="ecommerce",
        aliases=[Alias(text="ExampleKart", lang="en", script="latin", kind="legal")],
        officialDomains=[
            OfficialDomain(domain=d, verifiedBy="admin", verifiedAt=datetime.now(UTC))
            for d in official_domains
        ],
    )


class _Body:
    """A minimal stand-in for a POST /brands/{id}/official-contacts request body."""

    def __init__(self, e164, display, contact_types, source, authority, scope=None):
        self.e164 = e164
        self.display = display
        self.contactTypes = contact_types
        self.source = source
        self.authority = authority
        self.scope = scope


_requested_authority = st.one_of(st.none(), st.sampled_from(list(Authority)))
_domain_matches = st.booleans()


# Feature: aslinumber-p2-tenancy-brands, Property 7: Official-contact
# creation sets correct defaults, including the authority rule
@settings(max_examples=100)
@given(domain_matches=_domain_matches, requested=_requested_authority)
def test_resolve_authority_follows_the_authority_rule(domain_matches: bool, requested) -> None:
    """resolve_authority honors requested when the source domain matches

    an official domain (defaulting to primary when omitted); otherwise
    rejects authority=primary and returns supporting for every other
    request.
    """
    official_domains = ["examplekart.test"]
    source_domain = "examplekart.test" if domain_matches else "unverified.test"

    if domain_matches:
        result = resolve_authority(requested, source_domain, official_domains)
        expected = requested if requested is not None else Authority.PRIMARY
        assert result == expected
    elif requested == Authority.PRIMARY:
        try:
            resolve_authority(requested, source_domain, official_domains)
            raised = False
        except AppError as exc:
            raised = True
            assert exc.code == ErrorCode.VALIDATION_ERROR
            assert exc.status_code == 422
        assert raised
    else:
        result = resolve_authority(requested, source_domain, official_domains)
        assert result == Authority.SUPPORTING


@settings(max_examples=100)
@given(domain_matches=_domain_matches, requested=_requested_authority)
def test_prepare_official_contact_create_sets_fixed_defaults(
    domain_matches: bool, requested
) -> None:
    """Regardless of requested values, method is always manual and status

    is always active with validFrom set at creation time, for every
    accepted request.
    """
    official_domains = ["examplekart.test"]
    brand = _make_brand(official_domains)
    source_domain = "examplekart.test" if domain_matches else "unverified.test"
    body = _Body(
        e164="+919876543210",
        display="Support",
        contact_types=["support"],
        source=ContactSource(
            url=f"https://{source_domain}/contact", registeredDomain=source_domain
        ),
        authority=requested,
    )

    if not domain_matches and requested == Authority.PRIMARY:
        try:
            prepare_official_contact_create(brand.tenantId, brand, body)
            raised = False
        except AppError:
            raised = True
        assert raised
        return

    before = datetime.now(UTC)
    contact = prepare_official_contact_create(brand.tenantId, brand, body)
    after = datetime.now(UTC)

    assert contact.method == ContactMethod.MANUAL
    assert contact.status == ContactStatus.ACTIVE
    assert before <= contact.validFrom <= after
