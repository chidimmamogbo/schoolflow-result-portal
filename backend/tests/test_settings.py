"""Tests for the app settings (decision D-020: fail fast on missing or invalid values).

Behaviour: the app refuses to start when a required setting is missing or
invalid, debug is on only for local development, and secret values never
appear when the settings object is printed or logged.

Each test builds its own environment with `monkeypatch` and passes
`env_file=None`, so your real backend/.env never affects the result.
"""

import pytest
from pydantic import ValidationError

from schoolflow_api.settings import Settings, load_settings

VALID_ENV = {
    "APP_ENV": "local",
    "APP_BASE_URL": "http://localhost:3000",
    "APP_SECRET_KEY": "test-only-secret-key-that-is-long-enough-123",
    "DATABASE_URL": "postgresql+psycopg://app_user:test_pw_123@localhost:5432/schoolflow",
}


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    """Start every test from a valid environment; tests then break one value."""
    for name in (*VALID_ENV, "DATABASE_URL_MIGRATIONS", "TEST_DATABASE_URL"):
        monkeypatch.delenv(name, raising=False)
    for name, value in VALID_ENV.items():
        monkeypatch.setenv(name, value)
    return monkeypatch


def load() -> Settings:
    return load_settings(env_file=None)


def test_valid_settings_load(env: pytest.MonkeyPatch) -> None:
    settings = load()

    assert settings.app_env == "local"
    assert settings.debug is True


@pytest.mark.parametrize("app_env", ["staging", "production"])
def test_debug_is_off_outside_local(env: pytest.MonkeyPatch, app_env: str) -> None:
    env.setenv("APP_ENV", app_env)

    assert load().debug is False


@pytest.mark.parametrize("missing", list(VALID_ENV))
def test_missing_required_setting_refuses_to_start(env: pytest.MonkeyPatch, missing: str) -> None:
    env.delenv(missing)

    with pytest.raises(ValidationError) as error:
        load()

    assert missing.lower() in str(error.value)


def test_unknown_app_env_is_rejected(env: pytest.MonkeyPatch) -> None:
    env.setenv("APP_ENV", "dev")

    with pytest.raises(ValidationError):
        load()


def test_short_secret_key_is_rejected(env: pytest.MonkeyPatch) -> None:
    env.setenv("APP_SECRET_KEY", "too-short")

    with pytest.raises(ValidationError):
        load()


@pytest.mark.parametrize(
    "url",
    [
        "sqlite:///schoolflow.db",  # never SQLite (D-030)
        "postgresql://app_user:pw@localhost/schoolflow",  # wrong driver: we use psycopg 3
        "mysql+pymysql://u:pw@localhost/schoolflow",
    ],
)
def test_database_url_must_be_postgres_with_psycopg(env: pytest.MonkeyPatch, url: str) -> None:
    env.setenv("DATABASE_URL", url)

    with pytest.raises(ValidationError):
        load()


def test_secrets_are_hidden_when_printed(env: pytest.MonkeyPatch) -> None:
    settings = load()
    shown = f"{settings!r} {settings!s}"

    assert "test-only-secret-key" not in shown
    assert "test_pw_123" not in shown
    # The real values are still there for the code that needs them.
    assert settings.database_url.get_secret_value().endswith("/schoolflow")
