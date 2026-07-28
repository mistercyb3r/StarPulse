import type { OutageSummaryResponse } from "../api/types";
import { formatMinutes } from "../utils/format";
import { OutageTimeline } from "./charts/OutageTimeline";
import { InfoCard } from "./InfoCard";

interface OutageHistoryCardProps {
  outages: OutageSummaryResponse | null;
}

function pluralize(count: number, noun: string): string {
  return `${count} ${noun}${count === 1 ? "" : "s"}`;
}

export function OutageHistoryCard({ outages }: OutageHistoryCardProps) {
  const totalDowntime = outages?.total_downtime_minutes_last_7d ?? null;

  return (
    <InfoCard
      title="📡 Connection History"
      subtitle="Outages and degraded-connection events, last 7 days"
      rows={[
        { label: "Today", value: outages ? pluralize(outages.outages_today, "outage") : "—" },
        { label: "Last 7 Days", value: outages ? pluralize(outages.outages_last_7d, "outage") : "—" },
        {
          label: "Total Downtime",
          value: formatMinutes(totalDowntime),
          tone: totalDowntime !== null && totalDowntime > 0 ? "warn" : "good",
        },
      ]}
      footer={<OutageTimeline events={outages?.events ?? []} />}
    />
  );
}
