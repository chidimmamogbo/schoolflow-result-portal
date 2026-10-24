"""App settings, read from environment variables (and backend/.env locally).

Decision D-020: the app refuses to start with missing or invalid settings, so a
mistake in Vercel's environment settings shows up at once as a clear error,
not later as a strange failure in the middle of a request. Names match
backend/.env.example. Settings for email, payments and Sentry join here when
their modules are built.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, HttpUrl, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# SQLAlchemy reads the driver from the URL: "+psycopg" means psycopg 3 (D-017).
POSTGRES_PSYCOPG_PREFIX = "postgresql+psycopg://"


def must_be_postgres_with_psycopg(value: SecretStr | None) -> SecretStr | None:
    if value is not None and not value.get_secret_value().startswith(POSTGRES_PSYCOPG_PREFIX):
        # The message names the expected format, never the value itself.
        raise ValueError(f"must start with {POSTGRES_PSYCOPG_PREFIX}")
    return value


ENV_CONFIG = SettingsConfigDict(
    env_file=".env",
    env_file_encoding="utf-8",
    # backend/.env may hold names for modules not built yet; ignore them
    # here rather than crash. Each module adds its own required fields.
    extra="ignore",
)


class Settings(BaseSettings):
    model_config = ENV_CONFIG

    app_env: Literal["local", "staging", "production"]
    app_base_url: HttpUrl
    # SecretStr prints as "**********", so secrets never leak into logs.
    app_secret_key: SecretStr = Field(min_length=32)
    database_url: SecretStr
    # The super admin's pages only (role app_platform, D-051). Without it those pages
    # answer 503 (making it required needs a CHANGE: an existing test omits it).
    database_url_platform: SecretStr | None = None
    # The public verification page only (role app_verifier, D-076): it can call
    # verify_report() and nothing else. Without it /verify answers 503.
    database_url_verifier: SecretStr | None = None
    database_url_migrations: SecretStr | None = None
    test_database_url: SecretStr | None = None

    _check_urls = field_validator(
        "database_url",
        "database_url_platform",
        "database_url_verifier",
        "database_url_migrations",
        "test_database_url",
    )(must_be_postgres_with_psycopg)

    @property
    def debug(self) -> bool:
        """Debug output and the /docs page only on your own machine (D-020)."""
        return self.app_env == "local"


class MigrationSettings(BaseSettings):
    """Only what Alembic needs, so migrations run without the app's other settings."""

    model_config = ENV_CONFIG

    database_url_migrations: SecretStr

    _check_url = field_validator("database_url_migrations")(must_be_postgres_with_psycopg)


def load_migration_settings(env_file: str | None = ".env") -> MigrationSettings:
    return MigrationSettings(_env_file=env_file)  # pyright: ignore[reportCallIssue]


def load_settings(env_file: str | None = ".env") -> Settings:
    """Read settings now; raises pydantic.ValidationError if any are missing or wrong."""
    # Pyright cannot see that the required fields come from the environment.
    return Settings(_env_file=env_file)  # pyright: ignore[reportCallIssue]


@lru_cache
def get_settings() -> Settings:
    """The settings the app uses, read once and then reused (like a PHP constant)."""
    return load_settings()
