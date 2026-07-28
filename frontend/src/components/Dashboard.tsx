import { useStarlinkTelemetry } from "../hooks/useStarlinkTelemetry";
import { formatBps, formatDuration, formatMs, formatPercent, formatRelativeTime } from "../utils/format";
import { ConnectionIndicator } from "./ConnectionIndicator";
import { ConnectionTimeline } from "./charts/ConnectionTimeline";
import { LatencyHistoryChart } from "./charts/LatencyHistoryChart";
import { SpeedHistoryChart } from "./charts/SpeedHistoryChart";
import "./Dashboard.css";
import { LoadingScreen } from "./LoadingScreen";
import { MetricCard, type MetricTone } from "./MetricCard";
import { MockDataBanner } from "./MockDataBanner";
import { StatusBadge } from "./StatusBadge";

function toneForThreshold(value: number | null | undefined, warnAt: number, badAt: number): MetricTone {
  if (value === null || value === undefined) return "neutral";
  if (value >= badAt) return "bad";
  if (value >= warnAt) return "warn";
  return "good";
}

function toneForUptime(percent: number | null | undefined): MetricTone {
  if (percent === null || percent === undefined) return "neutral";
  if (percent >= 99) return "good";
  if (percent >= 95) return "warn";
  return "bad";
}

function statusLabel(state: string): string {
  if (state === "CONNECTED") return "Connected";
  if (state === "SEARCHING") return "Searching";
  if (state === "UNKNOWN") return "Unknown";
  return state.replaceAll("_", " ");
}

function statusSublabel(uptimeSeconds: number | null | undefined, starlinkConnected: boolean | null | undefined): string | undefined {
  if (starlinkConnected === false) return "Dish unreachable by collector";
  if (uptimeSeconds != null) return `Dish up ${formatDuration(uptimeSeconds)}`;
  return undefined;
}

export function Dashboard() {
  const { status, history, summary, health, isLoading, isUsingMockData, lastUpdated } = useStarlinkTelemetry();
  const samples = history?.samples ?? [];

  if (isLoading) {
    return <LoadingScreen message="Loading Starlink telemetry…" />;
  }

  return (
    <div className="dashboard">
      <header className="dashboard__header">
        <div>
          <h1 className="dashboard__title">StarPulse</h1>
          <p className="dashboard__subtitle">Local Starlink telemetry dashboard</p>
        </div>
        <div className="dashboard__header-meta">
          <ConnectionIndicator label={isUsingMockData ? "Backend Offline" : "Backend Online"} tone={isUsingMockData ? "bad" : "good"} />
          {status && <StatusBadge state={status.connection_state} />}
          <span className="dashboard__updated">Updated {formatRelativeTime(lastUpdated?.toISOString() ?? null)}</span>
        </div>
      </header>

      {isUsingMockData && <MockDataBanner />}

      <section className="dashboard__metrics">
        <MetricCard
          label="Status"
          value={status ? statusLabel(status.connection_state) : "—"}
          sublabel={statusSublabel(status?.uptime_seconds, health?.starlink_connected)}
          tone={status?.connection_state === "CONNECTED" ? "good" : "bad"}
        />
        <MetricCard label="Download" value={formatBps(status?.download_bps)} sublabel="current" />
        <MetricCard label="Upload" value={formatBps(status?.upload_bps)} sublabel="current" />
        <MetricCard
          label="Latency"
          value={formatMs(status?.latency_ms)}
          sublabel="current"
          tone={toneForThreshold(status?.latency_ms, 50, 100)}
        />
        <MetricCard
          label="Obstruction"
          value={formatPercent(status?.obstruction_percent)}
          sublabel="current"
          tone={toneForThreshold(status?.obstruction_percent, 1, 5)}
        />
        <MetricCard
          label="Uptime"
          value={formatPercent(summary?.uptime_percent)}
          sublabel="last 24h"
          tone={toneForUptime(summary?.uptime_percent)}
        />
      </section>

      <section className="dashboard__charts">
        <SpeedHistoryChart samples={samples} />
        <LatencyHistoryChart samples={samples} />
        <ConnectionTimeline samples={samples} />
      </section>

      <footer className="dashboard__footer">
        StarPulse is a local, self-hosted dashboard — no accounts, no cloud, data never leaves your network.
      </footer>
    </div>
  );
}
