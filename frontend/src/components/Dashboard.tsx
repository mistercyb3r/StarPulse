import { useStarlinkTelemetry } from "../hooks/useStarlinkTelemetry";
import { formatBps, formatMs, formatPercent, formatRelativeTime } from "../utils/format";
import { BrandMark, Tooltip } from "./BrandMark";
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
  appVersion?: string;
  onOpenWeatherImpact?: () => void;
  onOpenLocationSettings?: () => void;
  onOpenNotifications?: () => void;
  onOpenAbout?: () => void;
}

export function Dashboard({
  appVersion = "1.0.0",
  onOpenWeatherImpact,
  onOpenLocationSettings,
  onOpenNotifications,
  onOpenAbout,
}: DashboardProps) {
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
        <div className="dashboard__brand">
          <BrandMark size={40} version={appVersion} />
          <p className="dashboard__subtitle">Self-hosted Starlink monitoring</p>
        </div>
        <div className="dashboard__header-meta">
          <Tooltip text="Whether the StarPulse API is reachable from this browser">
            <ConnectionIndicator
              label={isUsingMockData ? "Backend Offline" : "Backend Online"}
              tone={isUsingMockData ? "bad" : "good"}
            />
          </Tooltip>
          {status && <StatusBadge state={status.connection_state} />}
          {health?.starlink_connected === false && (
            <Tooltip text="The collector could not reach the dish on the last poll">
              <ConnectionIndicator label="Dish Unreachable" tone="bad" />
            </Tooltip>
          )}
          <span className="dashboard__updated" title="Last successful dashboard refresh">
            Updated {formatRelativeTime(lastUpdated?.toISOString() ?? null)}
          </span>
          {onOpenWeatherImpact && (
            <button type="button" className="dashboard__nav-link" onClick={onOpenWeatherImpact}>
              🌦️ Weather Impact
            </button>
          )}
          {onOpenLocationSettings && (
            <button type="button" className="dashboard__nav-link" onClick={onOpenLocationSettings}>
              📍 Location
            </button>
          )}
          {onOpenNotifications && (
            <button type="button" className="dashboard__nav-link" onClick={onOpenNotifications}>
              🚨 Alerts
            </button>
          )}
          {onOpenAbout && (
            <button type="button" className="dashboard__nav-link" onClick={onOpenAbout}>
              About
            </button>
          )}
          <InstallPwaButton />
        </div>
      </header>

      {isUsingMockData && <MockDataBanner />}

      <StarlinkHealthCard health={starlinkHealth} />

      <section className="dashboard__metrics">
        <MetricCard label="Download" value={formatBps(status?.download_bps)} sublabel="current" icon="⬇️" />
        <MetricCard label="Upload" value={formatBps(status?.upload_bps)} sublabel="current" icon="⬆️" />
        <MetricCard
          label="Latency"
          value={formatMs(status?.latency_ms)}
          sublabel="current"
          tone={toneForThreshold(status?.latency_ms, 50, 100)}
          icon="📶"
        />
        <MetricCard
          label="Obstruction"
          value={formatPercent(status?.obstruction_percent)}
          sublabel="current"
          tone={toneForThreshold(status?.obstruction_percent, 1, 5)}
          icon="🛰️"
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
        <div className="dashboard__footer-brand">StarPulse v{appVersion}</div>
        <div>Self-hosted Starlink monitoring — no accounts, no cloud, data stays on your network.</div>
      </footer>
    </div>
  );
}
