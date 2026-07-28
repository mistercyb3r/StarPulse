"""Database access object used by the application and API layer."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

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
        """Create any tables that don't exist yet."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        Base.metadata.create_all(bind=self.engine)

    def get_session(self) -> Generator[Session, None, None]:
        """Yield a session, closing it afterwards. Usable as a FastAPI dependency."""
        session = self.session_factory()
        try:
            yield session
        finally:
            session.close()

    def dispose(self) -> None:
        self.engine.dispose()
