import type { WeatherResponse } from "../api/types";
import { formatPercent, formatRelativeTime, formatTemperature, formatWindSpeed } from "../utils/format";
import { InfoCard } from "./InfoCard";

interface WeatherCardProps {
  weather: WeatherResponse | null;
}

export function WeatherCard({ weather }: WeatherCardProps) {
  if (weather === null) {
    return <InfoCard title="🌤 Weather" rows={[]} unavailableMessage="Loading weather…" />;
  }

  if (!weather.available) {
    return <InfoCard title="🌤 Weather" rows={[]} unavailableMessage={weather.message ?? "Weather is unavailable"} />;
  }

  const locationLabel = weather.location_source === "dish_gps" ? "Dish GPS location" : "Configured location";

  return (
    <InfoCard
      title="🌤 Weather"
      subtitle={locationLabel}
      rows={[
        { label: "Temperature", value: formatTemperature(weather.temperature_c) },
        { label: "Feels Like", value: formatTemperature(weather.feels_like_c) },
        { label: "Humidity", value: formatPercent(weather.humidity_percent, 0) },
        { label: "Wind Speed", value: formatWindSpeed(weather.wind_speed_kph) },
        { label: "Conditions", value: weather.conditions ?? "—" },
      ]}
      footer={<span className="info-card__timestamp">Updated {formatRelativeTime(weather.fetched_at)}</span>}
    />
  );
}
