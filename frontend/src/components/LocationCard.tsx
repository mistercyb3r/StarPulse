import type { LocationResponse } from "../api/types";
import { InfoCard } from "./InfoCard";

interface LocationCardProps {
  location: LocationResponse | null;
}

function formatCoordinate(value: number | null | undefined, digits: number = 4): string {
  if (value === null || value === undefined) return "—";
  return `${value.toFixed(digits)}°`;
}

function gpsStatusLabel(location: LocationResponse): string {
  if (location.gps_enabled === false) return "Disabled";
  if (location.gps_valid === true) return "Locked";
  if (location.gps_valid === false) return "Searching";
  return "Unknown";
}

export function LocationCard({ location }: LocationCardProps) {
  if (location === null) {
    return <InfoCard title="📍 Location" rows={[]} unavailableMessage="Loading location…" />;
  }

  if (!location.available || !location.coordinates_collected) {
    return (
      <InfoCard
        title="📍 Location"
        rows={[
          { label: "GPS", value: gpsStatusLabel(location) },
          { label: "Coordinates", value: "Not collected yet" },
        ]}
      />
    );
  }

  const place =
    location.place_name
    ?? `${formatCoordinate(location.latitude)} ${formatCoordinate(location.longitude)}`;

  const rows = [
    { label: "Place", value: place },
    { label: "Source", value: location.source_label ?? location.source ?? "—" },
  ];
  if (location.altitude_m != null) {
    rows.push({ label: "Altitude", value: `${Math.round(location.altitude_m)} m` });
  }

  return (
    <InfoCard
      title="📍 Location"
      subtitle={
        location.place_name
          ? `Source: ${location.source_label ?? location.source ?? "—"}`
          : undefined
      }
      rows={rows}
    />
  );
}
