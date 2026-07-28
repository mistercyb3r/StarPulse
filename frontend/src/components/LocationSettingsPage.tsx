import { useCallback, useEffect, useState, type FormEvent } from "react";
import {
  ApiUnavailableError,
  ApiValidationError,
  clearSavedLocation,
  getLocationSettings,
  saveManualLocation,
  testLocationWeather,
} from "../api/client";
import { generateMockLocationSettings } from "../api/mockData";
import type { LocationSettingsResponse, WeatherResponse } from "../api/types";
import { formatTemperature, formatWindSpeed } from "../utils/format";
import "./LocationSettingsPage.css";

interface LocationSettingsPageProps {
  onBack: () => void;
}

export function LocationSettingsPage({ onBack }: LocationSettingsPageProps) {
  const [settings, setSettings] = useState<LocationSettingsResponse | null>(null);
  const [latitude, setLatitude] = useState("");
  const [longitude, setLongitude] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isBusy, setIsBusy] = useState(false);
  const [isMock, setIsMock] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<WeatherResponse | null>(null);

  const applySettings = useCallback((next: LocationSettingsResponse) => {
    setSettings(next);
    setLatitude(next.manual_latitude != null ? String(next.manual_latitude) : "");
    setLongitude(next.manual_longitude != null ? String(next.manual_longitude) : "");
  }, []);

  const refresh = useCallback(async () => {
    try {
      const next = await getLocationSettings();
      applySettings(next);
      setIsMock(false);
    } catch {
      const mock = generateMockLocationSettings();
      applySettings(mock);
      setIsMock(true);
    } finally {
      setIsLoading(false);
    }
  }, [applySettings]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function handleSave(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setMessage(null);
    setTestResult(null);

    const lat = Number(latitude.trim());
    const lon = Number(longitude.trim());
    if (!Number.isFinite(lat) || !Number.isFinite(lon)) {
      setError("Enter both latitude and longitude as numbers.");
      return;
    }
    if (lat < -90 || lat > 90 || lon < -180 || lon > 180) {
      setError("Latitude must be between -90 and 90; longitude between -180 and 180.");
      return;
    }

    setIsBusy(true);
    try {
      const response = await saveManualLocation({ latitude: lat, longitude: lon });
      applySettings(response.settings);
      setMessage(response.message);
      setIsMock(false);
    } catch (err) {
      setError(describeError(err));
    } finally {
      setIsBusy(false);
    }
  }

  async function handleTest() {
    setError(null);
    setMessage(null);
    setTestResult(null);

    const lat = Number(latitude.trim());
    const lon = Number(longitude.trim());
    if (!Number.isFinite(lat) || !Number.isFinite(lon)) {
      setError("Enter both latitude and longitude to test weather lookup.");
      return;
    }

    setIsBusy(true);
    try {
      const result = await testLocationWeather({ latitude: lat, longitude: lon });
      setTestResult(result);
      if (!result.available) {
        setError(result.message ?? "Weather lookup failed.");
      } else {
        setMessage("Weather lookup succeeded for these coordinates.");
      }
    } catch (err) {
      setError(describeError(err));
    } finally {
      setIsBusy(false);
    }
  }

  async function handleClear() {
    setError(null);
    setMessage(null);
    setTestResult(null);
    setIsBusy(true);
    try {
      const response = await clearSavedLocation();
      applySettings(response.settings);
      setMessage(response.message);
      setIsMock(false);
    } catch (err) {
      setError(describeError(err));
    } finally {
      setIsBusy(false);
    }
  }

  return (
    <div className="location-settings">
      <header className="location-settings__header">
        <div>
          <button type="button" className="location-settings__back" onClick={onBack}>
            ← Dashboard
          </button>
          <h1 className="location-settings__title">Location Settings</h1>
          <p className="location-settings__subtitle">
            Choose how StarPulse resolves weather location. Starlink GPS stays preferred when
            coordinates are available.
          </p>
        </div>
      </header>

      {isMock && (
        <p className="location-settings__banner" role="status">
          Showing sample location settings — backend unreachable.
        </p>
      )}

      {isLoading || !settings ? (
        <p className="location-settings__loading">Loading location settings…</p>
      ) : (
        <div className="location-settings__grid">
          <section className="location-settings__card">
            <h2 className="location-settings__card-title">Current location source</h2>
            <p className="location-settings__source">{formatSource(settings)}</p>
            {settings.place_name && <p className="location-settings__place">{settings.place_name}</p>}
            {settings.active_latitude != null && settings.active_longitude != null ? (
              <p className="location-settings__coords">
                {settings.active_latitude.toFixed(4)}°, {settings.active_longitude.toFixed(4)}°
              </p>
            ) : (
              <p className="location-settings__muted">{settings.message ?? "No coordinates available yet."}</p>
            )}
            <ul className="location-settings__status-list">
              <li>
                <span>Starlink GPS</span>
                <strong>{settings.dish_gps_available ? "Coordinates available" : "Not collected yet"}</strong>
              </li>
              <li>
                <span>Manual configuration</span>
                <strong>
                  {settings.manual_latitude != null && settings.manual_longitude != null
                    ? `${settings.manual_latitude.toFixed(4)}°, ${settings.manual_longitude.toFixed(4)}°`
                    : "Not set"}
                </strong>
              </li>
            </ul>
          </section>

          <section className="location-settings__card">
            <h2 className="location-settings__card-title">Manual coordinates</h2>
            <p className="location-settings__hint">
              Used as a fallback when the dish does not share GPS coordinates. Dish GPS remains
              preferred whenever it is available.
            </p>
            <form className="location-settings__form" onSubmit={handleSave}>
              <label className="location-settings__field">
                <span>Latitude</span>
                <input
                  type="number"
                  min={-90}
                  max={90}
                  step="0.0001"
                  value={latitude}
                  onChange={(event) => setLatitude(event.target.value)}
                  placeholder="e.g. 52.4130"
                  disabled={isBusy}
                />
              </label>
              <label className="location-settings__field">
                <span>Longitude</span>
                <input
                  type="number"
                  min={-180}
                  max={180}
                  step="0.0001"
                  value={longitude}
                  onChange={(event) => setLongitude(event.target.value)}
                  placeholder="e.g. 0.7480"
                  disabled={isBusy}
                />
              </label>
              <div className="location-settings__actions">
                <button type="submit" className="location-settings__primary" disabled={isBusy}>
                  {isBusy ? "Working…" : "Save location"}
                </button>
                <button type="button" className="location-settings__secondary" onClick={() => void handleTest()} disabled={isBusy}>
                  Test weather lookup
                </button>
                <button type="button" className="location-settings__danger" onClick={() => void handleClear()} disabled={isBusy}>
                  Clear saved location
                </button>
              </div>
            </form>

            {error && <p className="location-settings__error">{error}</p>}
            {message && <p className="location-settings__success">{message}</p>}

            {testResult?.available && (
              <div className="location-settings__test-result">
                <strong>{testResult.conditions ?? "Weather"}</strong>
                <span>
                  {formatTemperature(testResult.temperature_c)} · {formatWindSpeed(testResult.wind_speed_kph)}
                </span>
              </div>
            )}
          </section>

          <section className="location-settings__card location-settings__card--privacy">
            <h2 className="location-settings__card-title">Privacy</h2>
            <p className="location-settings__privacy">{settings.privacy_note}</p>
          </section>
        </div>
      )}
    </div>
  );
}

function formatSource(settings: LocationSettingsResponse): string {
  if (settings.active_source === "dish_gps") return "🛰 Starlink GPS";
  if (settings.active_source === "configured") return "⚙ Manual configuration";
  if (settings.active_source === "stored") return "Last known (local cache)";
  return "No active source";
}

function describeError(err: unknown): string {
  if (err instanceof ApiValidationError) return "Please check the coordinates and try again.";
  if (err instanceof ApiUnavailableError) return "Could not reach the StarPulse API.";
  return "Something went wrong. Please try again.";
}
