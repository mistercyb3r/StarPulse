import type { StarlinkSummaryResponse, TelemetrySample } from "../api/types";
import { formatWatts } from "../utils/format";
import { InfoCard } from "./InfoCard";

interface PowerCardProps {
  current: TelemetrySample | null;
  stats: StarlinkSummaryResponse | null;
  periodLabel: string;
}

export function PowerCard({ current, stats, periodLabel }: PowerCardProps) {
  return (
    <InfoCard
      title="⚡ Power"
      subtitle={`Average/min/max over ${periodLabel.toLowerCase()}`}
      rows={[
        { label: "Current", value: formatWatts(current?.power_watts) },
        { label: "Average", value: formatWatts(stats?.average_power_watts) },
        { label: "Minimum", value: formatWatts(stats?.min_power_watts) },
        { label: "Peak", value: formatWatts(stats?.max_power_watts) },
      ]}
    />
  );
}
