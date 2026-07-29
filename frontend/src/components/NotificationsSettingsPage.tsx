import type { FormEvent } from "react";
import { useEffect, useState } from "react";
import {
  ApiUnavailableError,
  ApiValidationError,
  getNotificationHistory,
  getNotificationSettings,
  saveNotificationSettings,
  testNotificationEmail,
} from "../api/client";
import type { NotificationHistoryItem, NotificationSettingsResponse } from "../api/types";
import "./NotificationsSettingsPage.css";

interface NotificationsSettingsPageProps {
  onBack: () => void;
}

const EMPTY: NotificationSettingsResponse = {
  enabled: false,
  smtp_host: "",
  smtp_port: 587,
  smtp_user: "",
  smtp_password_set: false,
  smtp_from: "",
  smtp_to: "",
  smtp_use_tls: true,
  cooldown_seconds: 900,
  latency_warn_ms: 100,
  packet_loss_warn: 0.1,
  obstruction_warn_percent: 5,
  health_warn_score: 50,
  smtp_configured: false,
};

export function NotificationsSettingsPage({ onBack }: NotificationsSettingsPageProps) {
  const [settings, setSettings] = useState<NotificationSettingsResponse>(EMPTY);
  const [password, setPassword] = useState("");
  const [history, setHistory] = useState<NotificationHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([getNotificationSettings(), getNotificationHistory(30)])
      .then(([next, hist]) => {
        if (!cancelled) {
          setSettings(next);
          setHistory(hist.events);
        }
      })
      .catch(() => {
        if (!cancelled) setError("Could not load notification settings.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      const result = await saveNotificationSettings({
        enabled: settings.enabled,
        smtp_host: settings.smtp_host,
        smtp_port: settings.smtp_port,
        smtp_user: settings.smtp_user,
        smtp_password: password || undefined,
        smtp_from: settings.smtp_from,
        smtp_to: settings.smtp_to,
        smtp_use_tls: settings.smtp_use_tls,
        cooldown_seconds: settings.cooldown_seconds,
        latency_warn_ms: settings.latency_warn_ms,
        packet_loss_warn: settings.packet_loss_warn,
        obstruction_warn_percent: settings.obstruction_warn_percent,
        health_warn_score: settings.health_warn_score,
      });
      setSettings(result.settings);
      setPassword("");
      setMessage(result.message);
      const hist = await getNotificationHistory(30);
      setHistory(hist.events);
    } catch (err) {
      setError(err instanceof ApiValidationError || err instanceof ApiUnavailableError ? err.message : "Save failed.");
    } finally {
      setSaving(false);
    }
  }

  async function onTest() {
    setTesting(true);
    setError(null);
    setMessage(null);
    try {
      const result = await testNotificationEmail();
      setMessage(result.message);
      const hist = await getNotificationHistory(30);
      setHistory(hist.events);
      if (!result.ok) setError(result.message);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Test email failed.");
    } finally {
      setTesting(false);
    }
  }

  return (
    <div className="notif-page">
      <header className="notif-page__header">
        <button type="button" className="notif-page__back" onClick={onBack}>
          ← Dashboard
        </button>
        <div>
          <h1 className="notif-page__title">🚨 Email Notifications</h1>
          <p className="notif-page__subtitle">SMTP alerts for Starlink offline, recovery, and performance warnings.</p>
        </div>
      </header>

      {loading ? (
        <p className="notif-page__muted">Loading…</p>
      ) : (
        <>
          <form className="notif-page__card" onSubmit={onSubmit}>
            <label className="notif-page__toggle">
              <input
                type="checkbox"
                checked={settings.enabled}
                onChange={(e) => setSettings({ ...settings, enabled: e.target.checked })}
              />
              Enable email notifications
            </label>

            <div className="notif-page__grid">
              <label>
                SMTP host
                <input
                  value={settings.smtp_host}
                  onChange={(e) => setSettings({ ...settings, smtp_host: e.target.value })}
                  placeholder="smtp.example.com"
                  autoComplete="off"
                />
              </label>
              <label>
                SMTP port
                <input
                  type="number"
                  value={settings.smtp_port}
                  onChange={(e) => setSettings({ ...settings, smtp_port: Number(e.target.value) })}
                />
              </label>
              <label>
                Username
                <input
                  value={settings.smtp_user}
                  onChange={(e) => setSettings({ ...settings, smtp_user: e.target.value })}
                  autoComplete="username"
                />
              </label>
              <label>
                Password {settings.smtp_password_set ? "(saved — leave blank to keep)" : ""}
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete="new-password"
                  placeholder={settings.smtp_password_set ? "••••••••" : ""}
                />
              </label>
              <label>
                From
                <input
                  value={settings.smtp_from}
                  onChange={(e) => setSettings({ ...settings, smtp_from: e.target.value })}
                  placeholder="alerts@example.com"
                />
              </label>
              <label>
                To
                <input
                  value={settings.smtp_to}
                  onChange={(e) => setSettings({ ...settings, smtp_to: e.target.value })}
                  placeholder="you@example.com"
                />
              </label>
              <label>
                Cooldown (seconds)
                <input
                  type="number"
                  value={settings.cooldown_seconds}
                  onChange={(e) => setSettings({ ...settings, cooldown_seconds: Number(e.target.value) })}
                  title="Minimum time between emails of the same alert type"
                />
              </label>
              <label className="notif-page__toggle">
                <input
                  type="checkbox"
                  checked={settings.smtp_use_tls}
                  onChange={(e) => setSettings({ ...settings, smtp_use_tls: e.target.checked })}
                />
                Use STARTTLS
              </label>
            </div>

            <h2 className="notif-page__section-title">Warning thresholds</h2>
            <div className="notif-page__grid">
              <label title="Alert when latency exceeds this value">
                Latency warn (ms)
                <input
                  type="number"
                  value={settings.latency_warn_ms}
                  onChange={(e) => setSettings({ ...settings, latency_warn_ms: Number(e.target.value) })}
                />
              </label>
              <label title="Alert when packet loss fraction exceeds this (0.1 = 10%)">
                Packet loss warn (0–1)
                <input
                  type="number"
                  step="0.01"
                  value={settings.packet_loss_warn}
                  onChange={(e) => setSettings({ ...settings, packet_loss_warn: Number(e.target.value) })}
                />
              </label>
              <label title="Alert when obstruction percentage exceeds this">
                Obstruction warn (%)
                <input
                  type="number"
                  value={settings.obstruction_warn_percent}
                  onChange={(e) => setSettings({ ...settings, obstruction_warn_percent: Number(e.target.value) })}
                />
              </label>
              <label title="Alert when health score falls below this">
                Health warn score
                <input
                  type="number"
                  value={settings.health_warn_score}
                  onChange={(e) => setSettings({ ...settings, health_warn_score: Number(e.target.value) })}
                />
              </label>
            </div>

            <div className="notif-page__actions">
              <button type="submit" disabled={saving}>
                {saving ? "Saving…" : "Save settings"}
              </button>
              <button type="button" className="notif-page__secondary" onClick={onTest} disabled={testing}>
                {testing ? "Sending…" : "Send test email"}
              </button>
            </div>

            {message && <p className="notif-page__ok">{message}</p>}
            {error && <p className="notif-page__error">{error}</p>}
            <p className="notif-page__muted">
              Status: {settings.smtp_configured ? "SMTP looks configured" : "SMTP incomplete"} · Cooldown prevents spam
              between identical alert types.
            </p>
          </form>

          <section className="notif-page__card">
            <h2 className="notif-page__section-title">Recent notification history</h2>
            {history.length === 0 ? (
              <p className="notif-page__muted">No notifications recorded yet.</p>
            ) : (
              <ul className="notif-page__history">
                {history.map((item) => (
                  <li key={item.id}>
                    <div className="notif-page__history-top">
                      <strong>{item.subject}</strong>
                      <span className={`notif-page__status notif-page__status--${item.status}`}>{item.status}</span>
                    </div>
                    <div className="notif-page__muted">
                      {new Date(item.timestamp).toLocaleString()} · {item.event_type}
                      {item.error_message ? ` · ${item.error_message}` : ""}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </>
      )}
    </div>
  );
}
