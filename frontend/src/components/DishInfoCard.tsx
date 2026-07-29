import type { DishInfoResponse } from "../api/types";
import { formatDuration } from "../utils/format";
import { ChartCard } from "./charts/ChartCard";
import "./DishInfoCard.css";

function gpsStatusLabel(info: DishInfoResponse | null): string {
  if (!info) return "—";
  if (info.gps_enabled === false) return "Disabled";
  if (info.gps_valid === true) return "Locked";
  if (info.gps_valid === false) return "Searching";
  return "Unknown";
}

function formatDegrees(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return `${value.toFixed(1)}°`;
}

interface DishInfoCardProps {
  info: DishInfoResponse | null;
}

export function DishInfoCard({ info }: DishInfoCardProps) {
  const rows: Array<[string, string]> = [
    ["Model", info?.hardware_version ?? "—"],
    ["Software", info?.software_version ?? "—"],
    ["Dish Uptime", formatDuration(info?.uptime_seconds)],
    ["GPS Status", gpsStatusLabel(info)],
    ["Satellites", info?.gps_satellites != null ? String(info.gps_satellites) : "—"],
    ["Azimuth", formatDegrees(info?.azimuth_deg)],
    ["Elevation", formatDegrees(info?.elevation_deg)],
  ];

  return (
    <ChartCard title="🖥️ Dish Information" subtitle="Hardware, GPS, and pointing details">
      <dl className="dish-info">
        {rows.map(([label, value]) => (
          <div className="dish-info__row" key={label}>
            <dt className="dish-info__label">{label}</dt>
            <dd className="dish-info__value">{value}</dd>
          </div>
        ))}
      </dl>
    </ChartCard>
  );
}
