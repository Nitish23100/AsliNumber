"""Brand_Service: slug/domain validation, the Authority_Rule, and creation orchestration.

Implements the design's ``backend/app/services/brand_service.py`` component:
``SLUG_PATTERN``, ``validate_slug``, ``validate_registrable_domain`` (task 5.1);
``validate_brand_create`` (task 5.4); ``resolve_authority`` and
``prepare_official_contact_create`` (task 5.7).

``validate_registrable_domain`` uses a module-level ``tldextract.TLDExtract``
instance constructed with ``suffix_list_urls=()``, so domain validation
never makes a network call to fetch the public suffix list -- it relies
entirely on the snapshot bundled with the ``tldextract`` package. This
keeps the function fast and deterministic in tests and CI, at the cost of
not picking up newly-added public suffixes until the dependency itself is
upgraded, which is an acceptable tradeoff for this phase's validation use
case (confirming a plausible registrable domain, not resolving DNS).
"""

import re
from datetime import UTC, datetime

import tldextract
from pydantic import BaseModel

from app.core.errors import AppError, ErrorCode
from app.models.brand import Authority, Brand, ContactMethod, ContactStatus
from app.models.official_contact import ContactScope, ContactSource, OfficialContact
from app.repos.brands_repo import BrandsRepo


def _coerce(value, model_cls):
    """Build `model_cls` from `value`, whatever shape `value` already is.

    `value` may already be an instance of `model_cls` (returned as-is), a
    different Pydantic model with the same field shape (e.g. a router's
    own request sub-model), or a plain dict -- in the latter two cases a
    fresh `model_cls` instance is built from its data.
    """
    if isinstance(value, model_cls):
        return value
    if isinstance(value, BaseModel):
        return model_cls(**value.model_dump())
    return model_cls(**value)


SLUG_PATTERN = re.compile(r"^[a-z0-9-]{2,40}$")

# ``suffix_list_urls=()`` disables fetching a fresh public suffix list over
# the network; the bundled snapshot shipped with the package is used
# instead, per this module's docstring above.
_tld_extractor = tldextract.TLDExtract(suffix_list_urls=())

# RFC 2606 reserves these TLDs for documentation/testing use; none of
# them appear in the public suffix list (since no real domain can be
# registered under them), so plain tldextract resolution treats
# ``examplekart.test`` the same as a genuinely unregistrable string. This
# project's own fictional demo-brand convention (Requirement 12.2,
# docs/design.md Sec13) depends on ``.test``-TLD domains validating as
# registrable, so they are special-cased here as a second recognized
# "suffix" category alongside the real public suffix list.
_RFC_2606_RESERVED_TLDS = frozenset({"test", "example", "invalid", "localhost"})


def validate_slug(slug: str) -> None:
    """Raise ``AppError(VALIDATION_ERROR)`` if ``slug`` doesn't match ``SLUG_PATTERN``.

    Per Requirement 2.1 / Property 1: a brand-creation request is accepted
    only if its slug matches ``^[a-z0-9-]{2,40}$``.
    """
    if not SLUG_PATTERN.match(slug):
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            f"{slug!r} is not a valid brand slug; expected ^[a-z0-9-]{{2,40}}$.",
        )


def validate_registrable_domain(domain: str) -> str:
    """Confirm ``domain`` resolves to a non-empty registered domain.

    Per Requirement 2.5 / Property 3: a candidate domain is accepted as an
    ``officialDomains`` entry only if ``tldextract`` resolves it to a
    non-empty registered domain (e.g. ``example.com``, not a bare TLD, an
    unregistrable suffix, or a non-domain string). Returns the normalized
    registered domain on success; raises ``AppError(VALIDATION_ERROR)``
    otherwise.
    """
    extracted = _tld_extractor(domain)
    registered_domain = extracted.top_domain_under_public_suffix

    if (
        not registered_domain
        and extracted.subdomain
        and (extracted.domain.lower() in _RFC_2606_RESERVED_TLDS)
    ):
        # tldextract parses an unrecognized apex label as `domain` and
        # everything above it as `subdomain` (e.g. for "examplekart.test":
        # subdomain="examplekart", domain="test"). The registrable name
        # under the reserved pseudo-TLD is the last label of `subdomain`
        # plus `domain`, e.g. "examplekart.test" or, for
        # "sub.examplekart.test", still "examplekart.test".
        last_label = extracted.subdomain.rsplit(".", 1)[-1]
        registered_domain = f"{last_label}.{extracted.domain}"

    if not registered_domain:
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            f"{domain!r} is not a registrable domain.",
        )
    return registered_domain


def validate_brand_create(tenant_id, body, brands_repo: BrandsRepo) -> None:
    """Orchestrate every Requirement 2 validation rule for brand creation.

    Order, per the design: slug pattern -> slug uniqueness (via
    ``brands_repo.find_by_slug``) -> non-empty ``aliases`` -> non-empty
    ``officialDomains`` -> each domain registrable. ``body`` is expected
    to expose ``slug``, ``aliases``, and ``officialDomains`` attributes
    (e.g. a Pydantic request model or a ``Brand`` instance under
    construction).
    """
    validate_slug(body.slug)

    if brands_repo.find_by_slug(tenant_id, body.slug) is not None:
        raise AppError(
            ErrorCode.CONFLICT,
            f"A brand with slug {body.slug!r} already exists for this tenant.",
        )

    if len(body.aliases) == 0:
        raise AppError(ErrorCode.VALIDATION_ERROR, "aliases must contain at least one entry.")

    if len(body.officialDomains) == 0:
        raise AppError(
            ErrorCode.VALIDATION_ERROR, "officialDomains must contain at least one entry."
        )

    for official_domain in body.officialDomains:
        validate_registrable_domain(official_domain.domain)


def resolve_authority(
    requested: Authority | None,
    source_domain: str,
    official_domains: list[str],
) -> Authority:
    """Implement the Authority_Rule (Requirement 4.3-4.5 / Property 7).

    When ``source_domain``'s registered-domain form is one of
    ``official_domains``, honors ``requested`` (defaulting to
    ``Authority.PRIMARY`` when omitted -- a verified-domain source has no
    reason to default to ``supporting``). Otherwise, raises
    ``AppError(VALIDATION_ERROR)`` if ``requested == Authority.PRIMARY``,
    else returns ``Authority.SUPPORTING``.
    """
    if source_domain in official_domains:
        return requested if requested is not None else Authority.PRIMARY

    if requested == Authority.PRIMARY:
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            "authority=primary requires source.registeredDomain to match one of the "
            "brand's officialDomains.",
        )
    return Authority.SUPPORTING


def prepare_official_contact_create(
    tenant_id,
    brand: Brand,
    body,
) -> OfficialContact:
    """Build a ready-to-persist ``OfficialContact`` from a creation request.

    Per Requirement 4.2, 4.3, 4.4, 4.5, 4.6 / Property 7: orchestrates
    ``resolve_authority`` plus the fixed ``method=manual``,
    ``status=active``, ``validFrom=now`` defaults, regardless of any
    other value supplied in ``body``. ``body`` is expected to expose
    ``e164``, ``display``, ``contactTypes``, ``scope`` (optional),
    ``source``, and an optional requested ``authority``.
    """
    source = _coerce(body.source, ContactSource)
    scope = _coerce(body.scope, ContactScope) if body.scope is not None else None

    official_domains = [d.domain for d in brand.officialDomains]
    authority = resolve_authority(body.authority, source.registeredDomain, official_domains)

    return OfficialContact(
        tenantId=tenant_id,
        brandId=brand.id,
        e164=body.e164,
        display=body.display,
        contactTypes=body.contactTypes,
        scope=scope,
        authority=authority,
        method=ContactMethod.MANUAL,
        source=source,
        retrievedAt=datetime.now(UTC),
        status=ContactStatus.ACTIVE,
        validFrom=datetime.now(UTC),
        validTo=None,
    )
