# Changelog

All notable changes to StarPulse are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-07-29

### Added
- Email notification system (SMTP) for Starlink offline, recovered, high latency,
  packet loss, high obstruction, and server health warnings
- Notification enable/disable settings, test email button, per-event cooldown,
  and notification history stored in SQLite
- About page with version, GitHub link, system information, and credits
- StarPulse logo (SVG), favicon, and PWA app icons
- Dashboard header branding with version + connection status; footer with
  StarPulse v1.0 tagline

### Changed
- Dashboard visual polish: section icons, spacing, card styling, status colours,
  and helpful tooltips (layout unchanged)
- Version bumped to 1.0.0 across backend and frontend
- README updated for Docker deployment, backup, and update guidance

### Notes
- Discord, Telegram, SMS, and mobile push are intentionally out of scope for v1.0
