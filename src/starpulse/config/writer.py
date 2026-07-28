"""Writes updates back to ``config.toml``.

``settings.py`` only ever reads configuration (via the read-only stdlib
``tomllib``); this module is the one place StarPulse persists changes
made through the API — currently just the first-run setup wizard
(``starpulse.api.routes.setup``).

Rewriting the file with ``tomli_w`` means hand-written comments in a
previously generated ``config.toml`` are lost the first time a section
is updated this way. That's a deliberate, documented trade-off in favor
of always producing a valid, correctly-typed file instead of patching
text with regexes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import tomli_w
import tomllib


def update_config_file(config_file: Path, updates: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    """Merge ``updates`` into ``config_file`` and rewrite it, returning the result.

    ``updates`` is a mapping of section name to a mapping of keys to set
    within that section, e.g. ``{"starlink": {"dish_host": "10.0.0.1"}}``.
    Sections/keys not mentioned are left untouched.
    """
    current: dict[str, Any] = {}
    if config_file.exists():
        with config_file.open("rb") as f:
            current = tomllib.load(f)

    for section, values in updates.items():
        current.setdefault(section, {})
        current[section].update(values)

    config_file.parent.mkdir(parents=True, exist_ok=True)
    with config_file.open("wb") as f:
        tomli_w.dump(current, f)

    return current
