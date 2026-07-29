import type { WeatherResponse } from "../api/types";
import { formatPercent, formatRelativeTime, formatTemperature, formatWindSpeed } from "../utils/format";
import { ChartCard } from "./charts/ChartCard";
import { InfoCard } from "./InfoCard";
import "./WeatherCard.css";

interface WeatherCardProps {
  weather: WeatherResponse | null;
  onSetupLocation?: () => void;
}

function isLocationRequired(message: string | null | undefined): boolean {
  if (!message) return false;
  const lower = message.toLowerCase();
  return lower.includes("location required") || lower.includes("no location");
}

export function WeatherCard({ weather, onSetupLocation }: WeatherCardProps) {
  if (weather === null) {
    return <InfoCard title="🌦️ Weather" rows={[]} unavailableMessage="Loading weather…" />;
  }

  if (!weather.available && isLocationRequired(weather.message)) {
    return (
      <ChartCard title="🌦️ Weather">
        <p className="weather-card__empty">No location configured.</p>
        {onSetupLocation && (
          <div className="weather-card__actions">
            <button type="button" className="weather-card__action" onClick={onSetupLocation}>
              Detect location
            </button>
            <button type="button" className="weather-card__action" onClick={onSetupLocation}>
              Enter manually
            </button>
          </div>
        )}
      </ChartCard>
    );
  }

  if (!weather.available) {
    return <InfoCard title="🌦️ Weather" rows={[]} unavailableMessage={weather.message ?? "Weather is unavailable"} />;
  }

  const locationLabel =
    weather.location_source === "dish_gps"
      ? "Starlink GPS"
      : weather.location_source === "geoip"
        ? "Approximate IP location"
        : weather.location_source === "stored"
          ? "Last known location"
          : "Manual configuration";

  return (
    <InfoCard
      title="🌦️ Weather"
      subtitle={weather.conditions ? `${weather.conditions} · ${locationLabel}` : locationLabel}
      rows={[
        { label: "Temperature", value: formatTemperature(weather.temperature_c) },
        { label: "Wind", value: formatWindSpeed(weather.wind_speed_kph) },
        {
          label: "Rain",
          value: formatPercent(weather.precipitation_probability, 0),
        },
        { label: "Feels Like", value: formatTemperature(weather.feels_like_c) },
        { label: "Humidity", value: formatPercent(weather.humidity_percent, 0) },
      ]}
      footer={<span className="info-card__timestamp">Updated {formatRelativeTime(weather.fetched_at)}</span>}
    />
  );
}
