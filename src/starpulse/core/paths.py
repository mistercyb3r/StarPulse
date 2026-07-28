"""Filesystem locations used by StarPulse.

StarPulse is local-first: everything it writes (config, database, logs)
lives under a single "data directory" so the whole install can be backed
up, moved, or mounted as one Docker volume.
"""

from __future__ import annotations

import os
from pathlib import Path

DATA_DIR_ENV_VAR = "STARPULSE_DATA_DIR"
DEFAULT_DATA_DIR_NAME = "data"


def get_data_dir(override: str | os.PathLike[str] | None = None) -> Path:
    """Resolve the StarPulse data directory and make sure it exists.

    Resolution order: explicit ``override`` argument, then the
    ``STARPULSE_DATA_DIR`` environment variable, then ``./data`` relative
    to the current working directory.
    """
    if override is not None:
        data_dir = Path(override)
    elif DATA_DIR_ENV_VAR in os.environ:
        data_dir = Path(os.environ[DATA_DIR_ENV_VAR])
    else:
        data_dir = Path.cwd() / DEFAULT_DATA_DIR_NAME

    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir.resolve()


def get_config_file_path(data_dir: Path, override: str | os.PathLike[str] | None = None) -> Path:
    """Resolve the config.toml path, defaulting to <data_dir>/config.toml."""
    if override is not None:
        return Path(override).resolve()
    return data_dir / "config.toml"


def resolve_db_path(data_dir: Path, db_path: str) -> Path:
    """Resolve a (possibly relative) database path against the data dir."""
    path = Path(db_path)
    if not path.is_absolute():
        path = data_dir / path
    return path
