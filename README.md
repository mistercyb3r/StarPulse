# StarPulse

<p align="center">
  <img src="docs/branding/logo.png" alt="StarPulse" width="520"/>
</p>

<p align="center">
  <strong>Self-hosted Starlink monitoring dashboard</strong><br/>
  Telemetry · Weather · Outage tracking · Email alerts<br/>
  <em>Created by mistercyber</em>
</p>

<p align="center">
  <a href="#installation">Installation</a> ·
  <a href="#docker-setup">Docker</a> ·
  <a href="#features">Features</a> ·
  <a href="docs/RELEASE_NOTES_v1.0.md">v1.0 Release Notes</a> ·
  <a href="docs/GITHUB.md">GitHub settings</a> ·
  <a href="LICENSE">MIT License</a>
</p>

---

StarPulse is a **local-first** dashboard for your Starlink dish. Run it on a PC, Raspberry Pi, or home server and open it in a browser on your LAN — no cloud account, no external telemetry leaving your network.

Built with **FastAPI + React + SQLite + Docker**, in the spirit of tools like Home Assistant and Grafana.

## Features

- **Live telemetry** — download/upload, latency, obstruction, power, and dish health score
- **History charts** — speed, latency, power, and connection-state timeline
- **Outage tracking** — degraded connection events with 7-day summaries
- **Weather impact** — local weather correlated with Starlink performance
- **Location settings** — manual coordinates, GeoIP fallback, dish GPS when available
- **Email alerts** — SMTP notifications for offline, recovery, and performance warnings
- **First-run setup** — configure dish IP and polling in the browser
- **Installable PWA** — use the dashboard like a local app

## Screenshots

![StarPulse dashboard](docs/screenshots/dashboard.png)

## Installation

### Quick start (Docker)

```bash
git clone https://github.com/mistercyb3r/StarPulse.git
cd StarPulse
cp .env.example .env   # optional — change ports if needed
docker compose up -d --build
```

Open the dashboard: **http://localhost:8080**

API / docs: **http://localhost:8000** · **http://localhost:8000/docs**

On first launch you’ll get a short setup wizard (dish IP, poll interval). After that, the live dashboard appears.

### Requirements

| Method | Needs |
| --- | --- |
| **Docker** (recommended) | Docker Engine 24+ and Compose plugin |
| **Local development** | Python 3.11+, Node.js 20+ / npm |

Your machine should be on the same LAN as the dish (default `192.168.100.1`). Without a dish, the UI still loads and shows sample data.

### Local development

```bash
# Backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
python -m starpulse              # http://localhost:8000

# Frontend (second terminal)
cd frontend
npm install
npm run dev                      # http://localhost:5173 (proxies /api → :8000)
```

## Docker Setup

```bash
docker compose up -d --build
docker compose ps
docker compose logs -f backend
docker compose down              # keeps data volume
docker compose down -v           # deletes persisted data
```

| Service | Default URL | Env override |
| --- | --- | --- |
| Dashboard (frontend) | http://localhost:8080 | `STARPULSE_WEB_PORT` |
| API (backend) | http://localhost:8000 | `STARPULSE_PORT` |

Persistent state (`config.toml`, SQLite DB, logs) lives in the Docker volume **`starpulse-data`**.

### Update

```bash
git pull
docker compose up -d --build
```

Your data volume is untouched by rebuilds.

## Configuration

Precedence (highest first): **environment variables** → **`config.toml`** → built-in defaults.

Common settings:

| Setting | config.toml | Environment | Default |
| --- | --- | --- | --- |
| Dish host | `[starlink] dish_host` | `STARPULSE_DISH_HOST` | `192.168.100.1` |
| Poll interval | `[starlink] poll_interval_seconds` | `STARPULSE_POLL_INTERVAL_SECONDS` | `5.0` |
| API port | `[server] port` | `STARPULSE_PORT` | `8000` |
| Weather coords | `[weather] latitude/longitude` | `STARPULSE_WEATHER_*` | *(auto)* |
| Email alerts | `[notifications] …` | `STARPULSE_SMTP_*` | disabled |

See [`.env.example`](.env.example) for the full list. Env vars always win over values saved by the setup wizard.

## Notifications

StarPulse can email you when the link drops, recovers, or crosses performance thresholds.

1. Open **Alerts** in the dashboard (or edit `[notifications]` in `config.toml`)
2. Set SMTP host, port, credentials, from, and to
3. Enable notifications
4. Use **Send test email**

Supported events: Starlink offline / recovered, high latency, packet loss, high obstruction, server health warning. Per-event cooldown prevents spam; history is stored in SQLite.

## Backup and Restore

### Docker

```bash
# Backup
docker run --rm -v starpulse-data:/data -v "$PWD":/backup alpine \
  tar czf /backup/starpulse-backup.tgz -C /data .

# Restore (stop stack first)
docker compose down
docker run --rm -v starpulse-data:/data -v "$PWD":/backup alpine \
  tar xzf /backup/starpulse-backup.tgz -C /data
docker compose up -d
```

### Local install

Copy your data directory (default `./data`), especially `config.toml` and `starpulse.db`.

## Troubleshooting

**Dashboard shows “sample data” only**  
Backend unreachable. Check `docker compose ps` or `curl http://localhost:8000/api/health`.

**No live telemetry / dish unreachable**  
Confirm LAN reachability to `192.168.100.1:9200`, dish IP in setup/`config.toml`, and backend logs (`docker compose logs backend`).

**Setup wizard keeps returning**  
You’re using a different data directory/DB than before (local vs Docker). Stick to one `STARPULSE_DATA_DIR`.

**Port change in setup didn’t apply**  
Restart the backend after changing the listen port, then update `STARPULSE_PORT` / your browser URL.

**Compose build fails on unusual architectures**  
`grpcio` needs a wheel for your platform. Prefer 64-bit `linux/amd64` or `arm64`, or run the backend locally (Option B).

## Roadmap

Intentionally out of scope for v1.0:

- Authentication (trusted LAN assumed)
- Discord / Telegram / SMS / mobile push
- Long-term retention / downsampling policies
- Dish write/control commands (API is read-only)
- Multi-dish support

## Contributing

Issues and pull requests are welcome.

```bash
pip install -e ".[dev]"
pytest
cd frontend && npm install && npm run build
```

Please keep changes focused; don’t expand scope into the roadmap items above without discussion.

## License

MIT — see [LICENSE](LICENSE).

## Creator

**Created by mistercyber**

- GitHub: [mistercyb3r](https://github.com/mistercyb3r)
- Project: [StarPulse](https://github.com/mistercyb3r/StarPulse)

---

<p align="center">
  <img src="docs/branding/icon.svg" alt="StarPulse icon" width="64"/><br/>
  <sub>StarPulse v1.0 · Self-hosted Starlink monitoring</sub>
</p>
