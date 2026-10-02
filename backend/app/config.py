"""Application configuration.

Defines :class:`Settings`, a ``pydantic-settings`` model covering every
environment variable this phase (and the declared-but-unused-until-later
LLM variables from Requirement 14.2) needs, plus the DEMO_MODE startup
safety guard (Requirement 11, design Property 8).

Values are loaded from process environment variables first, falling back to
a ``.env`` file at the backend working directory when present (standard
``pydantic-settings`` behavior). ``.env.example`` itself is written in a
later task (16.1); this module only wires up the loading mechanism.
"""

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DemoModeStartupError(RuntimeError):
    """Raised when the DEMO_MODE startup safety guard refuses to start.

    Per Requirement 11.1 and design Property 8, the API SHALL refuse to
    start if and only if ``DEMO_MODE`` is true, the bind host is not
    ``127.0.0.1``, and ``READ_ONLY`` is not true. This exception carries a
    human-readable reason so the failure is loud (logged / visible on
    process exit) rather than silent, per the design's Error Handling
    section. Later code (the app factory in task 2.6) is expected to either
    let this propagate and abort the process, or catch it to log before
    re-raising.
    """


class Settings(BaseSettings):
    """Centralized application configuration.

    Covers every variable from Requirement 14 (the environment variable
    template), plus ``DEMO_MODE``, ``READ_ONLY``, and ``BIND_HOST`` which
    the startup guard (Requirement 11) depends on.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ------------------------------------------------------------------
    # Core application variables (Requirement 14.1)
    # ------------------------------------------------------------------
    MONGO_URI: str = "mongodb://localhost:27017/aslinumber"
    SERPAPI_API_KEY: str = ""
    JWT_SECRET: str = ""
    FERNET_KEY: str = ""
    REPLAY_MODE: bool = True
    DEMO_MODE: bool = True
    PUBLIC_MODE: bool = True
    LIVE_COLLECTION: bool = False
    CORS_ORIGINS: str = "http://localhost:5173"

    # ------------------------------------------------------------------
    # LLM / Groq variables (Requirement 14.2)
    # Declared but unused in P1, consistent with the plan's architecture
    # decision to use Groq instead of local Ollama.
    # ------------------------------------------------------------------
    LLM_PROVIDER: str = "groq"
    GROQ_API_KEY: str = ""
    LLM_BASE_URL: str = "https://api.groq.com/openai/v1"
    LLM_MODEL: str = "openai/gpt-oss-120b"
    LLM_TIMEOUT_SECONDS: int = 30

    # ------------------------------------------------------------------
    # Startup-guard inputs (Requirement 11)
    # ------------------------------------------------------------------
    BIND_HOST: str = "127.0.0.1"
    READ_ONLY: bool = False

    @model_validator(mode="after")
    def _enforce_demo_mode_startup_guard(self) -> "Settings":
        """Refuse to start in an unsafe demo configuration.

        Formula (design Property 8, Requirement 11.1-11.3): refuse to start
        if and only if ``DEMO_MODE`` is true, ``BIND_HOST`` is not
        ``127.0.0.1``, and ``READ_ONLY`` is not true. Every other
        combination allows the application to start.
        """
        if self.DEMO_MODE is True and self.BIND_HOST != "127.0.0.1" and self.READ_ONLY is not True:
            raise DemoModeStartupError(
                "Refusing to start: DEMO_MODE=true requires binding to "
                "127.0.0.1 or setting READ_ONLY=true. Current configuration "
                f"has BIND_HOST={self.BIND_HOST!r} and READ_ONLY={self.READ_ONLY!r}, "
                "which would expose seeded demo credentials on a non-local "
                "network interface. Set BIND_HOST=127.0.0.1, set "
                "READ_ONLY=true, or set DEMO_MODE=false to proceed."
            )
        return self
