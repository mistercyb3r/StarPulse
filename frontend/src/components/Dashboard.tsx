import { useStarlinkTelemetry } from "../hooks/useStarlinkTelemetry";
import { formatBps, formatMs, formatPercent, formatRelativeTime } from "../utils/format";
import { ConnectionIndicator } from "./ConnectionIndicator";
import { ConnectionTimeline } from "./charts/ConnectionTimeline";
import { LatencyHistoryChart } from "./charts/LatencyHistoryChart";
import { PowerHistoryChart } from "./charts/PowerHistoryChart";
import { SpeedHistoryChart } from "./charts/SpeedHistoryChart";
import "./Dashboard.css";
import { DishInfoCard } from "./DishInfoCard";
import { InstallPwaButton } from "./InstallPwaButton";
import { LatencyStatsCard } from "./LatencyStatsCard";
import { LoadingScreen } from "./LoadingScreen";
import { LocationCard } from "./LocationCard";
import { MetricCard, type MetricTone } from "./MetricCard";
import { MockDataBanner } from "./MockDataBanner";
import { OutageHistoryCard } from "./OutageHistoryCard";
import { PerformanceStats, PERIOD_LABELS } from "./PerformanceStats";
import { PowerCard } from "./PowerCard";
import { SignalConditionsCard } from "./SignalConditionsCard";
import { StarlinkHealthCard } from "./StarlinkHealthCard";
import { StatusBadge } from "./StatusBadge";
import { WeatherCard } from "./WeatherCard";

function toneForThreshold(value: number | null | undefined, warnAt: number, badAt: number): MetricTone {
  if (value === null || value === undefined) return "neutral";
  if (value >= badAt) return "bad";
  if (value >= warnAt) return "warn";
  return "good";
}

interface DashboardProps {
  onOpenWeatherImpact?: () => void;
  onOpenLocationSettings?: () => void;
}

export function Dashboard({ onOpenWeatherImpact, onOpenLocationSettings }: DashboardProps) {
  const {
    status,
    history,
    health,
    starlinkHealth,
    dishInfo,
    performance,
    performancePeriod,
    setPerformancePeriod,
    weather,
    weatherImpact,
    location,
    outages,
    isLoading,
    isUsingMockData,
    lastUpdated,
  } = useStarlinkTelemetry();
  const samples = history?.samples ?? [];
  const periodLabel = PERIOD_LABELS[performancePeriod];

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
          {health?.starlink_connected === false && <ConnectionIndicator label="Dish Unreachable" tone="bad" />}
          <span className="dashboard__updated">Updated {formatRelativeTime(lastUpdated?.toISOString() ?? null)}</span>
          {onOpenWeatherImpact && (
            <button type="button" className="dashboard__nav-link" onClick={onOpenWeatherImpact}>
              Weather Impact
            </button>
          )}
          {onOpenLocationSettings && (
            <button type="button" className="dashboard__nav-link" onClick={onOpenLocationSettings}>
              Location
            </button>
          )}
          <InstallPwaButton />
        </div>
      </header>

      {isUsingMockData && <MockDataBanner />}

      <StarlinkHealthCard health={starlinkHealth} />

      <section className="dashboard__metrics">
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
      </section>

      <PerformanceStats performance={performance} period={performancePeriod} onPeriodChange={setPerformancePeriod} />

      <section className="dashboard__info-grid">
        <LocationCard location={location} onSetupLocation={onOpenLocationSettings} />
        <WeatherCard weather={weather} onSetupLocation={onOpenLocationSettings} />
        <SignalConditionsCard impact={weatherImpact} />
        <PowerCard current={status} stats={performance} periodLabel={periodLabel} />
        <LatencyStatsCard current={status} stats={performance} periodLabel={periodLabel} />
        <OutageHistoryCard outages={outages} />
      </section>

      <section className="dashboard__charts">
        <SpeedHistoryChart samples={samples} />
        <LatencyHistoryChart samples={samples} />
        <PowerHistoryChart samples={samples} />
        <ConnectionTimeline samples={samples} />
      </section>

      <DishInfoCard info={dishInfo} />

      <footer className="dashboard__footer">
        StarPulse is a local, self-hosted dashboard — no accounts, no cloud, data never leaves your network.
      </footer>
    </div>
  );
}
