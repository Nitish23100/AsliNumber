"""Unit tests for backend.app.core.errors.

Concrete examples covering the error envelope shape for each ErrorCode and
the AppError exception's conversion into that envelope, per the design's
Error Handling section (`{"error": {"code", "message", "details"}}`).
"""

import pytest

from app.core.errors import AppError, ErrorCode, build_error_envelope

ALL_CODES_AND_STATUSES = [
    (ErrorCode.VALIDATION_ERROR, 422),
    (ErrorCode.UNAUTHENTICATED, 401),
    (ErrorCode.FORBIDDEN, 403),
    (ErrorCode.RATE_LIMITED, 429),
    (ErrorCode.INTERNAL, 500),
]


@pytest.mark.parametrize(("code", "_status"), ALL_CODES_AND_STATUSES)
def test_build_error_envelope_shape_for_each_code(code: ErrorCode, _status: int) -> None:
    envelope = build_error_envelope(code, "something went wrong", {"field": "email"})

    assert set(envelope.keys()) == {"error"}
    assert set(envelope["error"].keys()) == {"code", "message", "details"}
    assert envelope["error"]["code"] == code.value
    assert envelope["error"]["message"] == "something went wrong"
    assert envelope["error"]["details"] == {"field": "email"}


def test_build_error_envelope_defaults_details_to_none() -> None:
    envelope = build_error_envelope(ErrorCode.INTERNAL, "boom")

    assert envelope["error"]["details"] is None


@pytest.mark.parametrize(("code", "expected_status"), ALL_CODES_AND_STATUSES)
def test_app_error_defaults_status_code_from_design_table(
    code: ErrorCode, expected_status: int
) -> None:
    error = AppError(code, "message")

    assert error.status_code == expected_status


def test_app_error_status_code_can_be_overridden() -> None:
    error = AppError(ErrorCode.UNAUTHENTICATED, "message", status_code=418)

    assert error.status_code == 418


def test_app_error_to_envelope_matches_build_error_envelope() -> None:
    error = AppError(ErrorCode.FORBIDDEN, "not allowed", details={"minimum": "admin"})

    envelope = error.to_envelope()

    expected = build_error_envelope(ErrorCode.FORBIDDEN, "not allowed", {"minimum": "admin"})
    assert envelope == expected


def test_app_error_is_an_exception_carrying_the_message() -> None:
    error = AppError(ErrorCode.INTERNAL, "unexpected failure")

    assert str(error) == "unexpected failure"
    assert isinstance(error, Exception)


def test_unauthenticated_errors_support_an_identical_generic_message() -> None:
    # Design note: refresh reuse must be indistinguishable from an
    # expired/unknown token in the response body -- both use UNAUTHENTICATED
    # with the same generic message. This module doesn't choose that
    # message (route code does), but confirms two AppErrors built with the
    # same code and message produce byte-identical envelopes, which is what
    # that indistinguishability relies on.
    expired_or_unknown = AppError(ErrorCode.UNAUTHENTICATED, "Invalid or expired credentials.")
    reused = AppError(ErrorCode.UNAUTHENTICATED, "Invalid or expired credentials.")

    assert expired_or_unknown.to_envelope() == reused.to_envelope()
