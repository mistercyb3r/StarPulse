# StarPulse v1.0 Release Notes

**Released:** 2026-07-29  
**Tag:** `v1.0.0`

StarPulse 1.0 is the first polished release of a self-hosted Starlink monitoring
stack: FastAPI + React + SQLite + Docker.

## Highlights

- Live dish telemetry dashboard with health, performance, weather impact, and outages
- Optional **email alerts** for offline/recovered and performance/health warnings
- Location settings (manual-first) and weather impact analysis
- Installable PWA with branded logo / favicon / app icons
- About page for version and system information

## Email notifications

Configure under **Alerts** in the dashboard (or `[notifications]` in `config.toml`):

1. Set SMTP host, port, credentials, from, and to
2. Enable notifications
3. Use **Send test email** to verify delivery
4. Cooldown limits repeat emails of the same event type

History is stored in SQLite (`notification_events`).

## Upgrade notes

- Existing `config.toml` files gain `[notifications]` defaults on next load merge
- Database creates `notification_events` automatically on startup (`create_all`)
- No architecture rewrite — FastAPI + React + SQLite + Docker unchanged

## Known non-goals (v1.0)

- No Discord / Telegram / SMS / mobile push
- No multi-user auth (trusted LAN assumed)
- No write/control dish commands

See `CHANGELOG.md` and `README.md` for full details.
