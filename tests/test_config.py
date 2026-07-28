from __future__ import annotations

from pathlib import Path

import pytest

from starpulse.config.settings import load_settings


def test_loading_creates_default_config_file(data_dir: Path) -> None:
    settings = load_settings(data_dir=data_dir, env={})

    assert settings.config_file.exists()
    assert settings.config_file == data_dir / "config.toml"
    assert settings.server.host == "0.0.0.0"
    assert settings.server.port == 8000
    assert settings.logging.level == "INFO"
    assert settings.database.path == "starpulse.db"
    assert settings.starlink.dish_host == "192.168.100.1"
    assert settings.starlink.dish_port == 9200
    assert settings.starlink.poll_interval_seconds == 5.0
    assert settings.weather.enabled is True
    assert settings.weather.latitude is None
    assert settings.weather.longitude is None
    assert settings.weather.cache_seconds == 600.0


def test_loading_is_idempotent(data_dir: Path) -> None:
    first = load_settings(data_dir=data_dir, env={})
    contents_after_first_load = first.config_file.read_text(encoding="utf-8")

    second = load_settings(data_dir=data_dir, env={})

    assert second.config_file.read_text(encoding="utf-8") == contents_after_first_load


def test_config_file_values_are_respected(data_dir: Path) -> None:
    data_dir.mkdir(parents=True)
    config_file = data_dir / "config.toml"
    config_file.write_text(
        """
        [server]
        host = "127.0.0.1"
        port = 9000

        [logging]
        level = "DEBUG"
        """,
        encoding="utf-8",
    )

    settings = load_settings(data_dir=data_dir, env={})

    assert settings.server.host == "127.0.0.1"
    assert settings.server.port == 9000
    assert settings.logging.level == "DEBUG"
    # Untouched sections still fall back to the built-in default.
    assert settings.database.path == "starpulse.db"


def test_env_vars_override_config_file(data_dir: Path) -> None:
    env = {
        "STARPULSE_HOST": "10.0.0.5",
        "STARPULSE_PORT": "9999",
        "STARPULSE_LOG_LEVEL": "WARNING",
        "STARPULSE_DB_PATH": "custom.db",
        "STARPULSE_DISH_HOST": "10.1.1.1",
        "STARPULSE_DISH_PORT": "9201",
        "STARPULSE_POLL_INTERVAL_SECONDS": "2.5",
    }

    settings = load_settings(data_dir=data_dir, env=env)

    assert settings.server.host == "10.0.0.5"
    assert settings.server.port == 9999
    assert isinstance(settings.server.port, int)
    assert settings.logging.level == "WARNING"
    assert settings.database.path == "custom.db"
    assert settings.starlink.dish_host == "10.1.1.1"
    assert settings.starlink.dish_port == 9201
    assert isinstance(settings.starlink.dish_port, int)
    assert settings.starlink.poll_interval_seconds == 2.5
    assert isinstance(settings.starlink.poll_interval_seconds, float)


def test_weather_env_vars_override_config_file(data_dir: Path) -> None:
    env = {
        "STARPULSE_WEATHER_ENABLED": "false",
        "STARPULSE_WEATHER_LATITUDE": "51.5074",
        "STARPULSE_WEATHER_LONGITUDE": "-0.1278",
    }

    settings = load_settings(data_dir=data_dir, env=env)

    assert settings.weather.enabled is False
    assert settings.weather.latitude == pytest.approx(51.5074)
    assert settings.weather.longitude == pytest.approx(-0.1278)


def test_weather_blank_coordinates_default_to_none(data_dir: Path) -> None:
    data_dir.mkdir(parents=True)
    config_file = data_dir / "config.toml"
    config_file.write_text('[weather]\nlatitude = ""\nlongitude = ""\n', encoding="utf-8")

    settings = load_settings(data_dir=data_dir, env={})

    assert settings.weather.latitude is None
    assert settings.weather.longitude is None


def test_explicit_config_file_override(tmp_path: Path, data_dir: Path) -> None:
    custom_config = tmp_path / "custom-config.toml"
    custom_config.write_text('[server]\nhost = "192.168.1.1"\n', encoding="utf-8")

    settings = load_settings(data_dir=data_dir, config_file=custom_config, env={})

    assert settings.config_file == custom_config.resolve()
    assert settings.server.host == "192.168.1.1"
