import { useEffect, useState, type FormEvent } from "react";
import { ApiValidationError, getSetupStatus, submitSetup } from "../api/client";
import {
  detectBrowserLocation,
  GeolocationDeniedError,
  GeolocationUnavailableError,
} from "../utils/geolocation";
import "./SetupWizard.css";

interface SetupWizardProps {
  onComplete: () => void;
}

interface FormState {
  dish_host: string;
  poll_interval_seconds: string;
  port: string;
  weather_latitude: string;
  weather_longitude: string;
}

const DEFAULT_FORM: FormState = {
  dish_host: "192.168.100.1",
  poll_interval_seconds: "5",
  port: "8000",
  weather_latitude: "",
  weather_longitude: "",
};

export function SetupWizard({ onComplete }: SetupWizardProps) {
  const [form, setForm] = useState<FormState>(DEFAULT_FORM);
  const [isLoadingDefaults, setIsLoadingDefaults] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [restartNotice, setRestartNotice] = useState<string | null>(null);
  const [detectHint, setDetectHint] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getSetupStatus()
      .then((status) => {
        if (cancelled) return;
        setForm({
          dish_host: status.dish_host,
          poll_interval_seconds: String(status.poll_interval_seconds),
          port: String(status.port),
          weather_latitude: status.weather_latitude != null ? String(status.weather_latitude) : "",
          weather_longitude: status.weather_longitude != null ? String(status.weather_longitude) : "",
        });
      })
      .catch(() => {
        // Backend unreachable while loading the form — keep the sensible
        // defaults already in state and let the user try submitting.
      })
      .finally(() => {
        if (!cancelled) setIsLoadingDefaults(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleDetectLocation() {
    setError(null);
    setDetectHint(null);
    try {
      const coords = await detectBrowserLocation();
      setForm((current) => ({
        ...current,
        weather_latitude: String(Math.round(coords.latitude * 10_000) / 10_000),
        weather_longitude: String(Math.round(coords.longitude * 10_000) / 10_000),
      }));
      setDetectHint("Location detected from this device. Save and continue to keep it.");
    } catch (err) {
      if (err instanceof GeolocationDeniedError) {
        setDetectHint("Permission denied — enter latitude and longitude manually if you want weather.");
      } else if (err instanceof GeolocationUnavailableError) {
        setDetectHint("Could not detect location — enter coordinates manually if you want weather.");
      } else {
        setDetectHint("Could not detect location — enter coordinates manually if you want weather.");
      }
    }
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setRestartNotice(null);
    setIsSubmitting(true);

    const latRaw = form.weather_latitude.trim();
    const lonRaw = form.weather_longitude.trim();
    const hasLat = latRaw !== "";
    const hasLon = lonRaw !== "";
    if (hasLat !== hasLon) {
      setError("Provide both weather latitude and longitude, or leave both blank to use dish GPS.");
      setIsSubmitting(false);
      return;
    }

    try {
      const payload = {
        dish_host: form.dish_host.trim(),
        poll_interval_seconds: Number(form.poll_interval_seconds),
        port: Number(form.port),
        ...(hasLat && hasLon
          ? { weather_latitude: Number(latRaw), weather_longitude: Number(lonRaw) }
          : {}),
      };
      const response = await submitSetup(payload);
      if (response.restart_required) {
        setRestartNotice(response.message);
      } else {
        onComplete();
      }
    } catch (err) {
      setError(
        err instanceof ApiValidationError
          ? describeValidationError(err.detail)
          : "Could not reach the StarPulse API. Make sure the backend is running, then try again.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  const fieldsDisabled = isLoadingDefaults || isSubmitting;

  return (
    <div className="setup-wizard">
      <div className="setup-wizard__card">
        <h1 className="setup-wizard__title">Welcome to StarPulse</h1>
        <p className="setup-wizard__subtitle">
          Let's connect to your Starlink dish. You can change these settings again later.
        </p>

        {restartNotice && (
          <div className="setup-wizard__notice">
            {restartNotice}{" "}
            <button type="button" className="setup-wizard__link-button" onClick={onComplete}>
              Continue to dashboard anyway
            </button>
          </div>
        )}

        <form className="setup-wizard__form" onSubmit={handleSubmit}>
          <label className="setup-wizard__field">
            <span>Starlink dish IP address</span>
            <input
              type="text"
              value={form.dish_host}
              onChange={(event) => setForm((current) => ({ ...current, dish_host: event.target.value }))}
              placeholder="192.168.100.1"
              disabled={fieldsDisabled}
              required
            />
          </label>

          <label className="setup-wizard__field">
            <span>Polling interval (seconds)</span>
            <input
              type="number"
              min="1"
              max="3600"
              step="0.5"
              value={form.poll_interval_seconds}
              onChange={(event) => setForm((current) => ({ ...current, poll_interval_seconds: event.target.value }))}
              disabled={fieldsDisabled}
              required
            />
          </label>

          <label className="setup-wizard__field">
            <span>Application port</span>
            <input
              type="number"
              min="1"
              max="65535"
              value={form.port}
              onChange={(event) => setForm((current) => ({ ...current, port: event.target.value }))}
              disabled={fieldsDisabled}
              required
            />
            <span className="setup-wizard__hint">Changing this requires restarting StarPulse afterwards.</span>
          </label>

          <label className="setup-wizard__field">
            <span>Weather latitude (optional)</span>
            <input
              type="number"
              min="-90"
              max="90"
              step="0.0001"
              value={form.weather_latitude}
              onChange={(event) => setForm((current) => ({ ...current, weather_latitude: event.target.value }))}
              placeholder="Recommended for reliable weather"
              disabled={fieldsDisabled}
            />
          </label>

          <label className="setup-wizard__field">
            <span>Weather longitude (optional)</span>
            <input
              type="number"
              min="-180"
              max="180"
              step="0.0001"
              value={form.weather_longitude}
              onChange={(event) => setForm((current) => ({ ...current, weather_longitude: event.target.value }))}
              placeholder="Recommended for reliable weather"
              disabled={fieldsDisabled}
            />
            <span className="setup-wizard__hint">
              Manual coordinates are preferred for weather. You can detect from this device, or leave
              blank to try approximate IP location later.
            </span>
          </label>

          <button
            type="button"
            className="setup-wizard__secondary"
            onClick={() => void handleDetectLocation()}
            disabled={fieldsDisabled}
          >
            Detect my location
          </button>
          {detectHint && <p className="setup-wizard__hint">{detectHint}</p>}

          {error && <p className="setup-wizard__error">{error}</p>}

          <button type="submit" className="setup-wizard__submit" disabled={fieldsDisabled}>
            {isSubmitting ? "Saving…" : "Save and continue"}
          </button>
        </form>
      </div>
    </div>
  );
}

function describeValidationError(detail: unknown): string {
  if (detail && typeof detail === "object" && "detail" in detail) {
    const inner = (detail as { detail: unknown }).detail;
    if (Array.isArray(inner)) {
      const messages = inner
        .map((item) => (item && typeof item === "object" && "msg" in item ? String((item as { msg: unknown }).msg) : null))
        .filter((msg): msg is string => Boolean(msg));
      if (messages.length > 0) return messages.join(", ");
    }
  }
  return "Please check the values you entered and try again.";
}
