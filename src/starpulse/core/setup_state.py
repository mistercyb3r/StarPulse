"""Tracks whether the first-run setup wizard has been completed.

Stored as a flag in the existing ``app_meta`` key/value table rather than
in ``config.toml`` — it's process/install state ("has a human confirmed
these settings?"), not a setting itself, so it shouldn't show up as a
config file value someone might expect to hand-edit.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from starpulse.db.models import AppMeta

SETUP_COMPLETE_KEY = "setup_completed"
_TRUE = "true"


def is_setup_complete(session: Session) -> bool:
    row = session.get(AppMeta, SETUP_COMPLETE_KEY)
    return row is not None and row.value == _TRUE


def mark_setup_complete(session: Session) -> None:
    row = session.get(AppMeta, SETUP_COMPLETE_KEY)
    if row is None:
        session.add(AppMeta(key=SETUP_COMPLETE_KEY, value=_TRUE))
    else:
        row.value = _TRUE
    session.commit()
