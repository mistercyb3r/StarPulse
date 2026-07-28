"""Configuration loading for StarPulse.

Precedence (highest wins): environment variables > config.toml >
built-in defaults. See ``.env.example`` for the list of supported
environment variables.
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any, Mapping

from pydantic import BaseModel

from starpulse.config.defaults import DEFAULT_CONFIG, DEFAULT_CONFIG_TOML
from starpulse.core.paths import get_config_file_path, get_data_dir

# Maps an environment variable name to the (section, key) it overrides.
_ENV_OVERRIDES: dict[str, tuple[str, str]] = {
    "STARPULSE_HOST": ("server", "host"),
    "STARPULSE_PORT": ("server", "port"),
    "STARPULSE_LOG_LEVEL": ("logging", "level"),
    "STARPULSE_LOG_FILE": ("logging", "file"),
    "STARPULSE_DB_PATH": ("database", "path"),
    "STARPULSE_DISH_HOST": ("starlink", "dish_host"),
    "STARPULSE_DISH_PORT": ("starlink", "dish_port"),
    "STARPULSE_POLL_INTERVAL_SECONDS": ("starlink", "poll_interval_seconds"),
}


class ServerSettings(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000


class LoggingSettings(BaseModel):
    level: str = "INFO"
    file: str = ""


class DatabaseSettings(BaseModel):
    path: str = "starpulse.db"


class StarlinkSettings(BaseModel):
    dish_host: str = "192.168.100.1"
    dish_port: int = 9200
    poll_interval_seconds: float = 5.0


class Settings(BaseModel):
    """Fully resolved StarPulse configuration."""

    data_dir: Path
    config_file: Path
    server: ServerSettings = ServerSettings()
    logging: LoggingSettings = LoggingSettings()
    database: DatabaseSettings = DatabaseSettings()
    starlink: StarlinkSettings = StarlinkSettings()


def _deep_merge(base: dict[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    """Recursively merge ``override`` onto a copy of ``base``."""
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, Mapping) and isinstance(merged.get(key), Mapping):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _ensure_config_file(config_file: Path) -> None:
    if not config_file.exists():
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text(DEFAULT_CONFIG_TOML, encoding="utf-8")


def _load_toml(config_file: Path) -> dict[str, Any]:
    with config_file.open("rb") as f:
        return tomllib.load(f)


def _apply_env_overrides(config: dict[str, Any], env: Mapping[str, str]) -> dict[str, Any]:
    result = {section: dict(values) for section, values in config.items()}
    for env_var, (section, key) in _ENV_OVERRIDES.items():
        if env_var in env:
            raw_value = env[env_var]
            result.setdefault(section, {})
            current = result[section].get(key)
            result[section][key] = _coerce_like(raw_value, current)
    return result


def _coerce_like(raw_value: str, reference: Any) -> Any:
    """Coerce a string env var value to match the type of ``reference``."""
    if isinstance(reference, bool):
        return raw_value.strip().lower() in {"1", "true", "yes", "on"}
    if isinstance(reference, int):
        return int(raw_value)
    if isinstance(reference, float):
        return float(raw_value)
    return raw_value


def load_settings(
    *,
    data_dir: str | os.PathLike[str] | None = None,
    config_file: str | os.PathLike[str] | None = None,
    env: Mapping[str, str] | None = None,
) -> Settings:
    """Load StarPulse settings from defaults, config.toml, then env vars.

    A config.toml is created with default values under the resolved data
    directory if one does not already exist.
    """
    env = os.environ if env is None else env

    resolved_data_dir = get_data_dir(data_dir if data_dir is not None else env.get("STARPULSE_DATA_DIR"))
    resolved_config_file = get_config_file_path(
        resolved_data_dir,
        config_file if config_file is not None else env.get("STARPULSE_CONFIG_FILE"),
    )

    _ensure_config_file(resolved_config_file)

    file_config = _load_toml(resolved_config_file)
    merged = _deep_merge(DEFAULT_CONFIG, file_config)
    merged = _apply_env_overrides(merged, env)

    return Settings(
        data_dir=resolved_data_dir,
        config_file=resolved_config_file,
        server=ServerSettings(**merged["server"]),
        logging=LoggingSettings(**merged["logging"]),
        database=DatabaseSettings(**merged["database"]),
        starlink=StarlinkSettings(**merged["starlink"]),
    )
