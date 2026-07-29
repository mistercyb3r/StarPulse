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
import {
  detectBrowserLocation,
  GeolocationDeniedError,
  GeolocationUnavailableError,
} from "../utils/geolocation";
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
  const [showAdvanced, setShowAdvanced] = useState(false);

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
      applySettings(generateMockLocationSettings());
      setIsMock(true);
    } finally {
      setIsLoading(false);
    }
  }, [applySettings]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function handleDetect() {
    setError(null);
    setMessage(null);
    setTestResult(null);
    setIsBusy(true);
    try {
      const coords = await detectBrowserLocation();
      setLatitude(String(roundCoord(coords.latitude)));
      setLongitude(String(roundCoord(coords.longitude)));
      setMessage("Browser location detected. Save coordinates to use them for weather.");
    } catch (err) {
      if (err instanceof GeolocationDeniedError) {
        setError("Location permission denied. You can enter latitude and longitude manually.");
      } else if (err instanceof GeolocationUnavailableError) {
        setError("Could not detect location in this browser. Enter coordinates manually.");
      } else {
        setError("Could not detect location. Enter coordinates manually.");
      }
    } finally {
      setIsBusy(false);
    }
  }

  async function handleSave(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setMessage(null);
    setTestResult(null);

    const parsed = parseCoords(latitude, longitude);
    if (!parsed) {
      setError("Enter both latitude and longitude as numbers.");
      return;
    }

    setIsBusy(true);
    try {
      const response = await saveManualLocation(parsed);
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

    const parsed = parseCoords(latitude, longitude);
    if (!parsed) {
      setError("Enter both latitude and longitude to test weather lookup.");
      return;
    }

    setIsBusy(true);
    try {
      const result = await testLocationWeather(parsed);
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
          <h1 className="location-settings__title">📍 Location</h1>
          <p className="location-settings__subtitle">
            Manual coordinates are the main way to configure weather. Browser detection and
            approximate IP location are available as helpers. Starlink GPS is an advanced fallback
            only.
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
            <h2 className="location-settings__card-title">Current source</h2>
            <p className="location-settings__source">{formatSource(settings)}</p>
            {settings.place_name && <p className="location-settings__place">{settings.place_name}</p>}
            {settings.active_latitude != null && settings.active_longitude != null ? (
              <p className="location-settings__coords">
                Coordinates: {settings.active_latitude.toFixed(4)}, {settings.active_longitude.toFixed(4)}
              </p>
            ) : (
              <p className="location-settings__muted">No location configured.</p>
            )}
            {settings.approximate && settings.accuracy && (
              <p className="location-settings__muted">Accuracy: {settings.accuracy}</p>
            )}
            <p className="location-settings__weather-status">
              Weather: {settings.weather_ok ? "Connected ✅" : settings.weather_summary ?? "Not connected"}
            </p>
          </section>

          <section className="location-settings__card">
            <h2 className="location-settings__card-title">Manual configuration</h2>
            <p className="location-settings__hint">
              Highest priority for weather. Detect from this device, or type coordinates yourself.
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
                  placeholder="e.g. 52.4128"
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
                  placeholder="e.g. 0.7471"
                  disabled={isBusy}
                />
              </label>
              <div className="location-settings__actions">
                <button type="button" className="location-settings__secondary" onClick={() => void handleDetect()} disabled={isBusy}>
                  Detect my location
                </button>
                <button type="submit" className="location-settings__primary" disabled={isBusy}>
                  Save coordinates
                </button>
                <button type="button" className="location-settings__secondary" onClick={() => void handleTest()} disabled={isBusy}>
                  Test weather
                </button>
                <button type="button" className="location-settings__danger" onClick={() => void handleClear()} disabled={isBusy}>
                  Clear location
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

          <section className="location-settings__card">
            <button
              type="button"
              className="location-settings__advanced-toggle"
              onClick={() => setShowAdvanced((value) => !value)}
            >
              {showAdvanced ? "Hide advanced diagnostics" : "Show advanced diagnostics"}
            </button>
            {showAdvanced && (
              <dl className="location-settings__diagnostics">
                <div>
                  <dt>Starlink GPS lock</dt>
                  <dd>{gpsLockLabel(settings)}</dd>
                </div>
                <div>
                  <dt>Dish coordinates</dt>
                  <dd>
                    {settings.dish_gps_available && settings.dish_latitude != null && settings.dish_longitude != null
                      ? `${settings.dish_latitude.toFixed(4)}, ${settings.dish_longitude.toFixed(4)}`
                      : "Not available"}
                  </dd>
                </div>
                {settings.advanced_note && (
                  <div>
                    <dt>Note</dt>
                    <dd>{settings.advanced_note}</dd>
                  </div>
                )}
              </dl>
            )}
          </section>
        </div>
      )}
    </div>
  );
}

function formatSource(settings: LocationSettingsResponse): string {
  if (settings.active_source === "configured") return "⚙ Manual configuration";
  if (settings.active_source === "geoip") return "🌍 Approximate IP location";
  if (settings.active_source === "dish_gps") return "🛰 Starlink GPS";
  if (settings.active_source === "stored") return "Last known (local cache)";
  return "Not configured";
}

function gpsLockLabel(settings: LocationSettingsResponse): string {
  if (settings.gps_enabled === false) return "Disabled";
  if (settings.gps_valid === true) return "Locked";
  if (settings.gps_valid === false) return "Searching";
  return "Unknown";
}

function parseCoords(latitude: string, longitude: string): { latitude: number; longitude: number } | null {
  const lat = Number(latitude.trim());
  const lon = Number(longitude.trim());
  if (!Number.isFinite(lat) || !Number.isFinite(lon)) return null;
  if (lat < -90 || lat > 90 || lon < -180 || lon > 180) return null;
  return { latitude: lat, longitude: lon };
}

function roundCoord(value: number): number {
  return Math.round(value * 10_000) / 10_000;
}

function describeError(err: unknown): string {
  if (err instanceof ApiValidationError) return "Please check the coordinates and try again.";
  if (err instanceof ApiUnavailableError) return "Could not reach the StarPulse API.";
  return "Something went wrong. Please try again.";
}
