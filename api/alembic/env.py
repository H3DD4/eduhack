"""Alembic env. Migrations run as the schema OWNER (MIGRATION_DATABASE_URL); the app runs as a non-superuser
role subject to row-level security (DATABASE_URL)."""
import os

from sqlalchemy import create_engine

import thinkfirst.models  # noqa: F401
from alembic import context
from thinkfirst.config import get_settings
from thinkfirst.core.db import Base, normalize_database_url

url = normalize_database_url(os.environ.get("MIGRATION_DATABASE_URL") or get_settings().database_url)
target_metadata = Base.metadata


def run_migrations_online() -> None:
    engine = create_engine(url)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, include_schemas=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True, include_schemas=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    run_migrations_online()
