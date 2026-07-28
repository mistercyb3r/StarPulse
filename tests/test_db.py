from __future__ import annotations

from pathlib import Path

from sqlalchemy import inspect

from starpulse.db.models import AppMeta
from starpulse.db.session import Database


def test_init_db_creates_tables(tmp_path: Path) -> None:
    db = Database(tmp_path / "test.db")

    db.init_db()

    inspector = inspect(db.engine)
    table_names = inspector.get_table_names()
    assert "app_meta" in table_names
    assert "telemetry_samples" in table_names
    assert (tmp_path / "test.db").exists()


def test_session_can_write_and_read(tmp_path: Path) -> None:
    db = Database(tmp_path / "test.db")
    db.init_db()

    session = next(db.get_session())
    try:
        session.add(AppMeta(key="schema_version", value="1"))
        session.commit()
    finally:
        session.close()

    session = next(db.get_session())
    try:
        row = session.get(AppMeta, "schema_version")
        assert row is not None
        assert row.value == "1"
    finally:
        session.close()


def test_creates_parent_directory_for_db_file(tmp_path: Path) -> None:
    nested_path = tmp_path / "nested" / "dir" / "test.db"
    db = Database(nested_path)

    db.init_db()

    assert nested_path.exists()
