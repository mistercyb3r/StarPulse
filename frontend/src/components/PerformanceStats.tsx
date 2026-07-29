import type { StarlinkSummaryResponse, SummaryPeriod } from "../api/types";
import { formatBps } from "../utils/format";
import { MetricCard } from "./MetricCard";
import "./PerformanceStats.css";

export const PERIOD_LABELS: Record<SummaryPeriod, string> = {
  "24h": "24 Hours",
  "7d": "7 Days",
  "30d": "30 Days",
};

const PERIODS: SummaryPeriod[] = ["24h", "7d", "30d"];

interface PerformanceStatsProps {
  performance: StarlinkSummaryResponse | null;
  period: SummaryPeriod;
  onPeriodChange: (period: SummaryPeriod) => void;
}

export function PerformanceStats({ performance, period, onPeriodChange }: PerformanceStatsProps) {
  const periodLabel = PERIOD_LABELS[period];

  return (
    <section className="performance-stats">
      <div className="performance-stats__header">
        <h3 className="performance-stats__title">📈 Performance</h3>
        <div className="performance-stats__periods" role="tablist" aria-label="Performance period">
          {PERIODS.map((value) => (
            <button
              key={value}
              type="button"
              role="tab"
              aria-selected={period === value}
              className={`performance-stats__period ${
                period === value ? "performance-stats__period--active" : ""
              }`}
              onClick={() => onPeriodChange(value)}
            >
              {PERIOD_LABELS[value]}
            </button>
          ))}
        </div>
      </div>

      <div className="performance-stats__grid">
        <MetricCard label="Avg Download" value={formatBps(performance?.average_download_bps)} sublabel={periodLabel} />
        <MetricCard label="Avg Upload" value={formatBps(performance?.average_upload_bps)} sublabel={periodLabel} />
        <MetricCard label="Peak Download" value={formatBps(performance?.peak_download_bps)} sublabel={periodLabel} />
        <MetricCard label="Peak Upload" value={formatBps(performance?.peak_upload_bps)} sublabel={periodLabel} />
      </div>
    </section>
  );
}
