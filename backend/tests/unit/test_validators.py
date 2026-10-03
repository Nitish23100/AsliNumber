"""Unit tests for backend.app.core.validators.

`mongomock` does not support `create_collection`'s validator option
(raises `NotImplementedError: Special options not supported`), so these
tests use `unittest.mock` to verify `apply_schema_validators` issues the
right commands for each branch (collection exists -> collMod; collection
absent -> create_collection) rather than depending on mongomock's
incomplete feature coverage. The real behavior (idempotent application
against an actual MongoDB deployment) was verified manually against the
project's Atlas cluster during development -- see task 1.6's own test for
the automated idempotency check using the same mocking approach.
"""

from unittest.mock import MagicMock

from app.core.validators import ENUM_PAIRS_FOR_DRIFT_TEST, apply_schema_validators


def test_apply_schema_validators_creates_missing_collections_with_validator() -> None:
    db = MagicMock()
    db.list_collection_names.return_value = []

    apply_schema_validators(db)

    created_names = {call.args[0] for call in db.create_collection.call_args_list}
    assert created_names == {"brands", "official_contacts", "audit_log"}
    for call in db.create_collection.call_args_list:
        assert call.kwargs["validationLevel"] == "moderate"
        assert "$jsonSchema" in call.kwargs["validator"]
    db.command.assert_not_called()


def test_apply_schema_validators_uses_collmod_for_existing_collections() -> None:
    db = MagicMock()
    db.list_collection_names.return_value = ["brands", "official_contacts", "audit_log"]

    apply_schema_validators(db)

    collmod_names = {call.args[1] for call in db.command.call_args_list}
    assert collmod_names == {"brands", "official_contacts", "audit_log"}
    for call in db.command.call_args_list:
        assert call.args[0] == "collMod"
        assert call.kwargs["validationLevel"] == "moderate"
    db.create_collection.assert_not_called()


def test_apply_schema_validators_is_idempotent_in_shape() -> None:
    """Applying twice issues the identical validator payload both times."""
    db = MagicMock()
    db.list_collection_names.return_value = ["brands", "official_contacts", "audit_log"]

    apply_schema_validators(db)
    first_calls = list(db.command.call_args_list)
    db.command.reset_mock()
    apply_schema_validators(db)
    second_calls = list(db.command.call_args_list)

    assert len(first_calls) == len(second_calls) == 3
    first_validators = sorted((c.args[1], c.kwargs["validator"]) for c in first_calls)
    second_validators = sorted((c.args[1], c.kwargs["validator"]) for c in second_calls)
    assert first_validators == second_validators


def test_enum_pairs_for_drift_test_values_match() -> None:
    """Every Pydantic enum's value set equals its schema property's enum list.

    Validates: Requirement 1.6. Not a Hypothesis property (the input
    space is a fixed, small set of 3 known enum/schema pairs, not an
    arbitrary generated input), so this is an example-based structural
    check per the design's Testing Strategy section.
    """
    assert len(ENUM_PAIRS_FOR_DRIFT_TEST) == 3
    for enum_cls, schema_values in ENUM_PAIRS_FOR_DRIFT_TEST:
        pydantic_values = {member.value for member in enum_cls}
        assert pydantic_values == set(schema_values), (
            f"{enum_cls.__name__} drifted from its $jsonSchema enum: "
            f"Pydantic has {pydantic_values}, schema has {set(schema_values)}"
        )
