import type { WeatherResponse } from "../api/types";
import { formatPercent, formatRelativeTime, formatTemperature, formatWindSpeed } from "../utils/format";
import { InfoCard } from "./InfoCard";

interface WeatherCardProps {
  weather: WeatherResponse | null;
}

export function WeatherCard({ weather }: WeatherCardProps) {
  if (weather === null) {
    return <InfoCard title="🌦 Weather" rows={[]} unavailableMessage="Loading weather…" />;
  }

  if (!weather.available) {
    return <InfoCard title="🌦 Weather" rows={[]} unavailableMessage={weather.message ?? "Weather is unavailable"} />;
  }

  const locationLabel =
    weather.location_source === "dish_gps"
      ? "Dish GPS location"
      : weather.location_source === "stored"
        ? "Last known location"
        : "Manual configuration";

  return (
    <InfoCard
      title="🌦 Weather"
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
