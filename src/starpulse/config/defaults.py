"""Built-in default configuration.

``DEFAULT_CONFIG_TOML`` is written out as ``config.toml`` the first time
StarPulse runs against a fresh data directory, so users get a real,
editable, commented file instead of hidden magic values.

``DEFAULT_CONFIG`` is the same data as a plain dict, used as the base that
a parsed config file (and then environment variables) get merged onto, so
missing keys always fall back to a sane default.
"""

from __future__ import annotations

from typing import Any

DEFAULT_CONFIG: dict[str, Any] = {
    "server": {
        "host": "0.0.0.0",
        "port": 8000,
    },
    "logging": {
        "level": "INFO",
        "file": "",
    },
    "database": {
        "path": "starpulse.db",
    },
    "starlink": {
        "dish_host": "192.168.100.1",
        "dish_port": 9200,
        "poll_interval_seconds": 5.0,
    },
    "weather": {
        "enabled": True,
        "latitude": "",
        "longitude": "",
        "cache_seconds": 600.0,
    },
}

DEFAULT_CONFIG_TOML = """\
# StarPulse configuration
#
# This file was generated automatically. Edit it to change how StarPulse
# runs, or override individual values with environment variables (see
# .env.example in the project root).

[server]
# Interface to bind the web server to. Use "127.0.0.1" to only allow
# connections from this machine, or "0.0.0.0" to allow access from your
# local network.
host = "0.0.0.0"
port = 8000

[logging]
# One of: DEBUG, INFO, WARNING, ERROR, CRITICAL
level = "INFO"
# Leave empty to log to the console only, or set a path to also log to a
# file (e.g. "starpulse.log", relative to this config file's directory).
file = ""

[database]
# Path to the SQLite database file. Relative paths are resolved against
# the data directory (the folder this config.toml lives in).
path = "starpulse.db"

[starlink]
# Address of the Starlink dish on your local network. 192.168.100.1 is
# the dish's default IP address on almost all installations.
dish_host = "192.168.100.1"
dish_port = 9200
# How often (in seconds) to poll the dish for telemetry. Lower values
# give more granular data at the cost of slightly more load on the dish.
poll_interval_seconds = 5.0

[weather]
# Shows current weather on the dashboard (via the free Open-Meteo API,
# no API key required).
enabled = true
# Leave blank to use the dish's own GPS position automatically when
# available (location sharing must be enabled on the dish). Setting
# coordinates here always overrides dish GPS, e.g.
# latitude = "51.5074", longitude = "-0.1278" for London.
latitude = ""
longitude = ""
# How long (in seconds) to cache weather API responses before refreshing.
cache_seconds = 600
"""
