"""Property-based tests for backend.app.config.Settings.

Hypothesis-based property test validating the DEMO_MODE startup safety
guard's formula (Requirement 11, design Property 8) across arbitrary
bind-host strings and both boolean flags. See tests/unit/test_config.py
for the concrete example-based tests covering the same guard.
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from app.config import DemoModeStartupError, Settings

# A non-empty, non-"127.0.0.1" bind-host strategy mixing arbitrary text with
# a few realistic-looking host values, so Hypothesis explores both "random
# junk" and plausible real-world bind addresses.
_arbitrary_non_localhost_bind_host = st.one_of(
    st.text(min_size=1, max_size=50).filter(lambda s: s != "127.0.0.1"),
    st.sampled_from(["0.0.0.0", "localhost", "192.168.1.1", "::", "example.com"]),
)


# Feature: aslinumber-p1-foundation, Property 8: Demo-mode startup guard is
# a total function of three inputs
@settings(max_examples=100)
@given(
    demo_mode=st.booleans(),
    bind_host=st.one_of(st.just("127.0.0.1"), _arbitrary_non_localhost_bind_host),
    read_only=st.booleans(),
)
def test_demo_mode_startup_guard_is_total_function_of_three_inputs(
    demo_mode: bool, bind_host: str, read_only: bool
) -> None:
    """The guard SHALL refuse to start iff DEMO_MODE and non-local bind and
    not READ_ONLY; every other combination SHALL allow startup.

    Validates: Requirements 11.1, 11.2, 11.3
    """
    should_refuse = demo_mode is True and bind_host != "127.0.0.1" and read_only is not True

    if should_refuse:
        try:
            Settings(DEMO_MODE=demo_mode, BIND_HOST=bind_host, READ_ONLY=read_only)
        except DemoModeStartupError:
            pass
        else:
            raise AssertionError(
                "Expected DemoModeStartupError for "
                f"DEMO_MODE={demo_mode!r}, BIND_HOST={bind_host!r}, "
                f"READ_ONLY={read_only!r}, but Settings construction succeeded."
            )
    else:
        settings_obj = Settings(DEMO_MODE=demo_mode, BIND_HOST=bind_host, READ_ONLY=read_only)
        assert settings_obj.DEMO_MODE is demo_mode
        assert bind_host == settings_obj.BIND_HOST
        assert settings_obj.READ_ONLY is read_only
