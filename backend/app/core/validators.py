"""MongoDB `$jsonSchema` collection validator application.

Implements the design's `backend/app/core/validators.py` component:
applies the `JSON_SCHEMA` constants co-located with each P2 model
(`app.models.brand`, `app.models.official_contact`,
`app.models.audit_log_entry`) to their respective collections at
`validationLevel: "moderate"`, per Requirement 1.4 and plan Sec7.1's
"enforced twice" convention (Pydantic at the application layer, a
MongoDB validator at the database layer).

`moderate` (rather than `strict`) means existing documents that predate
a validator are not retroactively checked, and updates to those
documents are not blocked by fields the validator doesn't recognize --
appropriate for a validator that is a second line of defense, not the
sole source of truth.
"""

from enum import Enum

from pymongo.database import Database
from pymongo.errors import OperationFailure

from app.models.audit_log_entry import JSON_SCHEMA as AUDIT_LOG_JSON_SCHEMA
from app.models.brand import JSON_SCHEMA as BRANDS_JSON_SCHEMA
from app.models.brand import Authority, ContactMethod, ContactStatus
from app.models.official_contact import JSON_SCHEMA as OFFICIAL_CONTACTS_JSON_SCHEMA

# Maps each collection name to its co-located JSON_SCHEMA constant. One
# place that lists every validator this phase applies, so
# `apply_schema_validators` and any future phase extending this list stay
# in sync without duplicating the mapping elsewhere.
_COLLECTION_SCHEMAS: dict[str, dict] = {
    "brands": BRANDS_JSON_SCHEMA,
    "official_contacts": OFFICIAL_CONTACTS_JSON_SCHEMA,
    "audit_log": AUDIT_LOG_JSON_SCHEMA,
}

# Pairs each Pydantic enum this phase introduces with the `enum` value
# list from its corresponding $jsonSchema property, consumed by the
# Requirement 1.6 drift test (task 1.5) so adding a new enum value in one
# layer without the other fails CI immediately, rather than silently
# accepting a value the database would reject (or vice versa).
ENUM_PAIRS_FOR_DRIFT_TEST: list[tuple[type[Enum], list[str]]] = [
    (Authority, OFFICIAL_CONTACTS_JSON_SCHEMA["properties"]["authority"]["enum"]),
    (ContactMethod, OFFICIAL_CONTACTS_JSON_SCHEMA["properties"]["method"]["enum"]),
    (ContactStatus, OFFICIAL_CONTACTS_JSON_SCHEMA["properties"]["status"]["enum"]),
]


def apply_schema_validators(db: Database) -> None:
    """Apply every P2 `$jsonSchema` validator, idempotently.

    For each collection in `_COLLECTION_SCHEMAS`: if the collection
    already exists, uses `collMod` to (re)apply the validator; otherwise
    creates the collection with the validator attached. Calling this
    function more than once (e.g. on every app startup) is safe and
    produces the same resulting validator document each time.
    """
    existing_collections = set(db.list_collection_names())

    for collection_name, schema in _COLLECTION_SCHEMAS.items():
        validator = {"$jsonSchema": schema}
        if collection_name in existing_collections:
            db.command(
                "collMod",
                collection_name,
                validator=validator,
                validationLevel="moderate",
            )
        else:
            try:
                db.create_collection(
                    collection_name,
                    validator=validator,
                    validationLevel="moderate",
                )
            except OperationFailure:
                # A concurrent apply_schema_validators call (or an earlier
                # call within the same process) may have already created
                # the collection between the list_collection_names() read
                # above and this create_collection() call. Re-applying via
                # collMod is the correct recovery, not a failure.
                db.command(
                    "collMod",
                    collection_name,
                    validator=validator,
                    validationLevel="moderate",
                )
