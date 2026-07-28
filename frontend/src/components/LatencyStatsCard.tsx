import type { StarlinkSummaryResponse, TelemetrySample } from "../api/types";
import { formatMs } from "../utils/format";
import { InfoCard } from "./InfoCard";

interface LatencyStatsCardProps {
  current: TelemetrySample | null;
  stats: StarlinkSummaryResponse | null;
  periodLabel: string;
}

export function LatencyStatsCard({ current, stats, periodLabel }: LatencyStatsCardProps) {
  return (
    <InfoCard
      title="📡 Latency"
      subtitle={`Best/worst over ${periodLabel.toLowerCase()}`}
      rows={[
        { label: "Current", value: formatMs(current?.latency_ms) },
        { label: `Average (${periodLabel})`, value: formatMs(stats?.average_latency_ms) },
        { label: "Best", value: formatMs(stats?.best_latency_ms), tone: "good" },
        { label: "Worst", value: formatMs(stats?.worst_latency_ms), tone: "warn" },
      ]}
    />
  );
}
