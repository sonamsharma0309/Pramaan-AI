"""Alembic environment: uses DATABASE_URL (SQLite by default, PostgreSQL when set)."""
import sqlalchemy as sa

from alembic import context
from backend import config
from backend.models import metadata

target_metadata = metadata


def run_migrations_offline() -> None:
    context.configure(url=config.DATABASE_URL, target_metadata=target_metadata, literal_binds=True, render_as_batch=config.IS_SQLITE)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = sa.create_engine(config.DATABASE_URL)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=config.IS_SQLITE)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
