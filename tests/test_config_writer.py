from __future__ import annotations

from pathlib import Path

from starpulse.config.settings import load_settings
from starpulse.config.writer import update_config_file


def test_update_config_file_creates_file_if_missing(tmp_path: Path) -> None:
    config_file = tmp_path / "config.toml"

    result = update_config_file(config_file, {"starlink": {"dish_host": "10.0.0.1"}})

    assert config_file.exists()
    assert result["starlink"]["dish_host"] == "10.0.0.1"


def test_update_config_file_preserves_untouched_sections(data_dir: Path) -> None:
    settings = load_settings(data_dir=data_dir, env={})

    update_config_file(settings.config_file, {"starlink": {"dish_host": "10.0.0.5"}})

    reloaded = load_settings(data_dir=data_dir, env={})
    assert reloaded.starlink.dish_host == "10.0.0.5"
    # Untouched sections/keys keep their previous values.
    assert reloaded.starlink.dish_port == 9200
    assert reloaded.server.port == 8000
    assert reloaded.database.path == "starpulse.db"


def test_update_config_file_merges_multiple_sections(data_dir: Path) -> None:
    settings = load_settings(data_dir=data_dir, env={})

    update_config_file(
        settings.config_file,
        {
            "starlink": {"dish_host": "10.0.0.9", "poll_interval_seconds": 2.0},
            "server": {"port": 9090},
        },
    )

    reloaded = load_settings(data_dir=data_dir, env={})
    assert reloaded.starlink.dish_host == "10.0.0.9"
    assert reloaded.starlink.poll_interval_seconds == 2.0
    assert reloaded.server.port == 9090
