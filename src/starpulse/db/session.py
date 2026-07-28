"""Database access object used by the application and API layer."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from starpulse.db import models  # noqa: F401  (registers models on Base.metadata)
from starpulse.db.base import Base, create_engine_for_path, create_session_factory


class Database:
    """Owns the SQLAlchemy engine and session factory for one StarPulse instance."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.engine = create_engine_for_path(self.db_path)
        self.session_factory = create_session_factory(self.engine)

    def init_db(self) -> None:
        """Create any tables that don't exist yet, and add any new columns to existing ones."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        Base.metadata.create_all(bind=self.engine)
        self._add_missing_columns()

    def _add_missing_columns(self) -> None:
        """Best-effort additive migration: ``ALTER TABLE ... ADD COLUMN`` for new nullable columns.

        StarPulse has no migration framework yet. This only ever adds
        columns that models.py declares but an existing on-disk database
        (created by an older version of StarPulse) doesn't have yet, so
        upgrades don't require deleting the database. It never renames,
        drops, or alters existing columns — if a future change needs more
        than that, this should be replaced with a real migration tool.
        """
        inspector = inspect(self.engine)
        existing_tables = set(inspector.get_table_names())

        with self.engine.begin() as conn:
            for table in Base.metadata.sorted_tables:
                if table.name not in existing_tables:
                    continue
                existing_columns = {col["name"] for col in inspector.get_columns(table.name)}
                for column in table.columns:
                    if column.name in existing_columns:
                        continue
                    ddl_type = column.type.compile(dialect=self.engine.dialect)
                    conn.execute(text(f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {ddl_type}'))

    def get_session(self) -> Generator[Session, None, None]:
        """Yield a session, closing it afterwards. Usable as a FastAPI dependency."""
        session = self.session_factory()
        try:
            yield session
        finally:
            session.close()

    def dispose(self) -> None:
        self.engine.dispose()
