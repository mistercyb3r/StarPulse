from __future__ import annotations

from pathlib import Path

from starpulse.core.setup_state import is_setup_complete, mark_setup_complete
from starpulse.db.session import Database


def test_setup_defaults_to_incomplete(tmp_path: Path) -> None:
    db = Database(tmp_path / "test.db")
    db.init_db()
    session = next(db.get_session())
    try:
        assert is_setup_complete(session) is False
    finally:
        session.close()


def test_mark_setup_complete_persists(tmp_path: Path) -> None:
    db = Database(tmp_path / "test.db")
    db.init_db()

    session = next(db.get_session())
    try:
        mark_setup_complete(session)
    finally:
        session.close()

    session = next(db.get_session())
    try:
        assert is_setup_complete(session) is True
    finally:
        session.close()


def test_mark_setup_complete_is_idempotent(tmp_path: Path) -> None:
    db = Database(tmp_path / "test.db")
    db.init_db()

    session = next(db.get_session())
    try:
        mark_setup_complete(session)
        mark_setup_complete(session)
        assert is_setup_complete(session) is True
    finally:
        session.close()
