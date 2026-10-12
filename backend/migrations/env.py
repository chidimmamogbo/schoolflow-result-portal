"""Alembic's start-up script: runs for every `alembic` command and migration.

Where the database address comes from, in order:
1. A connection handed over by Python code (the tests do this), or
2. The DATABASE_URL_MIGRATIONS environment variable (owner role, D-026);
   locally it is read from backend/.env.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import Connection, create_engine, pool

from schoolflow_api.models import Base
from schoolflow_api.settings import load_migration_settings

config = context.config

if config.config_file_name is not None:
    # Keep loggers the app already set up working (the default switches them off).
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def migrations_url() -> str:
    # Fails with a clear error if DATABASE_URL_MIGRATIONS is missing or not Postgres.
    return load_migration_settings().database_url_migrations.get_secret_value()


def configure(**options: object) -> None:
    context.configure(
        target_metadata=target_metadata,
        compare_server_default=True,  # also detect changed column defaults
        **options,  # pyright: ignore[reportArgumentType]
    )


def run_migrations_offline() -> None:
    """`alembic upgrade head --sql`: print the SQL for review instead of running it."""
    configure(url=migrations_url(), literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def run_with(connection: Connection) -> None:
    configure(connection=connection)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    given: Connection | None = config.attributes.get("connection")
    if given is not None:
        run_with(given)
        return
    engine = create_engine(migrations_url(), poolclass=pool.NullPool, hide_parameters=True)
    with engine.connect() as connection:
        run_with(connection)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
