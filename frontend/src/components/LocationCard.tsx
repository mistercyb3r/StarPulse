import type { LocationResponse } from "../api/types";
import { ChartCard } from "./charts/ChartCard";
import "./LocationCard.css";

interface LocationCardProps {
  location: LocationResponse | null;
  onSetupLocation?: () => void;
}

function formatSource(location: LocationResponse): string {
  if (location.source === "configured") return "Manual configuration";
  if (location.source === "geoip") return "Approximate IP location";
  if (location.source === "dish_gps") return "Starlink GPS";
  if (location.source === "stored") return "Last known";
  return location.source_label ?? "Unknown";
}

export function LocationCard({ location, onSetupLocation }: LocationCardProps) {
  if (location === null) {
    return (
      <ChartCard title="📍 Location">
        <p className="location-card__muted">Loading location…</p>
      </ChartCard>
    );
  }

  if (!location.available || !location.coordinates_collected) {
    return (
      <ChartCard title="📍 Location">
        <p className="location-card__place">Not configured</p>
        {onSetupLocation && (
          <button type="button" className="location-card__setup" onClick={onSetupLocation}>
            Setup
          </button>
        )}
      </ChartCard>
    );
  }

  const place =
    location.place_name
    ?? `${location.latitude?.toFixed(4)}, ${location.longitude?.toFixed(4)}`;

  return (
    <ChartCard title="📍 Location" subtitle={`Source: ${formatSource(location)}`}>
      <p className="location-card__place">{place}</p>
      {location.approximate && location.accuracy && (
        <p className="location-card__muted">Accuracy: {location.accuracy}</p>
      )}
      {onSetupLocation && (
        <button type="button" className="location-card__setup location-card__setup--subtle" onClick={onSetupLocation}>
          Change
        </button>
      )}
    </ChartCard>
  );
}
