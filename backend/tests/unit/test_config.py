"""Unit tests for backend.app.config.Settings.

Concrete examples covering the DEMO_MODE startup safety guard (Requirement
11, design Property 8). See tests/unit/test_config_properties.py (task 2.2)
for the Hypothesis-based property test validating the guard's formula
across arbitrary bind-host strings.
"""

import pytest

from app.config import DemoModeStartupError, Settings


def test_demo_mode_false_succeeds_regardless_of_bind_host() -> None:
    # DEMO_MODE=False never triggers the guard, no matter the bind host or
    # READ_ONLY value.
    settings = Settings(DEMO_MODE=False, BIND_HOST="0.0.0.0", READ_ONLY=False)

    assert settings.DEMO_MODE is False
    assert settings.BIND_HOST == "0.0.0.0"


def test_demo_mode_true_with_localhost_bind_succeeds() -> None:
    settings = Settings(DEMO_MODE=True, BIND_HOST="127.0.0.1", READ_ONLY=False)

    assert settings.DEMO_MODE is True
    assert settings.BIND_HOST == "127.0.0.1"


def test_demo_mode_true_with_non_local_bind_and_not_read_only_raises() -> None:
    with pytest.raises(DemoModeStartupError):
        Settings(DEMO_MODE=True, BIND_HOST="0.0.0.0", READ_ONLY=False)


def test_demo_mode_true_with_non_local_bind_and_read_only_succeeds() -> None:
    settings = Settings(DEMO_MODE=True, BIND_HOST="0.0.0.0", READ_ONLY=True)

    assert settings.DEMO_MODE is True
    assert settings.BIND_HOST == "0.0.0.0"
    assert settings.READ_ONLY is True
