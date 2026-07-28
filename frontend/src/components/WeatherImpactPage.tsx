import { useCallback, useEffect, useMemo, useState } from "react";
import {
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { getWeatherHistory } from "../api/client";
import { generateMockWeatherHistory } from "../api/mockData";
import type { WeatherHistoryPeriod, WeatherHistoryResponse } from "../api/types";
import { formatClockTime } from "../utils/format";
import { ChartCard } from "./charts/ChartCard";
import { ChartTooltip } from "./charts/ChartTooltip";
import { OutageTimeline } from "./charts/OutageTimeline";
import "./WeatherImpactPage.css";

const PERIODS: WeatherHistoryPeriod[] = ["24h", "7d", "30d"];
const PERIOD_LABELS: Record<WeatherHistoryPeriod, string> = {
  "24h": "24 Hours",
  "7d": "7 Days",
  "30d": "30 Days",
};

interface WeatherImpactPageProps {
  onBack: () => void;
}

export function WeatherImpactPage({ onBack }: WeatherImpactPageProps) {
  const [period, setPeriod] = useState<WeatherHistoryPeriod>("24h");
  const [history, setHistory] = useState<WeatherHistoryResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isMock, setIsMock] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const data = await getWeatherHistory(period);
      setHistory(data);
      setIsMock(false);
    } catch {
      setHistory(generateMockWeatherHistory(period));
      setIsMock(true);
    } finally {
      setIsLoading(false);
    }
  }, [period]);

  useEffect(() => {
    setIsLoading(true);
    void refresh();
  }, [refresh]);

  const chartData = useMemo(() => {
    if (!history) return [];
    const byTime = new Map<string, Record<string, number | string | null>>();

    for (const point of history.performance) {
      byTime.set(point.timestamp, {
        time: formatClockTime(point.timestamp),
        timestamp: point.timestamp,
        downloadMbps: point.average_download_bps == null ? null : Math.round((point.average_download_bps / 1_000_000) * 10) / 10,
        latencyMs: point.average_latency_ms,
        rainChance: null,
      });
    }

    for (const point of history.weather) {
      const existing = byTime.get(point.timestamp) ?? {
        time: formatClockTime(point.timestamp),
        timestamp: point.timestamp,
        downloadMbps: null,
        latencyMs: null,
        rainChance: null,
      };
      existing.rainChance = point.precipitation_probability;
      byTime.set(point.timestamp, existing);
    }

    return Array.from(byTime.values()).sort((a, b) => String(a.timestamp).localeCompare(String(b.timestamp)));
  }, [history]);

  return (
    <div className="weather-impact-page">
      <header className="weather-impact-page__header">
        <div>
          <button type="button" className="weather-impact-page__back" onClick={onBack}>
            ← Dashboard
          </button>
          <h1 className="weather-impact-page__title">Weather vs Performance</h1>
          <p className="weather-impact-page__subtitle">
            How rain, wind, and conditions correlate with Starlink speed and latency
          </p>
        </div>
        <div className="weather-impact-page__periods" role="tablist" aria-label="History period">
          {PERIODS.map((value) => (
            <button
              key={value}
              type="button"
              role="tab"
              aria-selected={period === value}
              className={`weather-impact-page__period ${period === value ? "weather-impact-page__period--active" : ""}`}
              onClick={() => setPeriod(value)}
            >
              {PERIOD_LABELS[value]}
            </button>
          ))}
        </div>
      </header>

      {isMock && (
        <div className="weather-impact-page__banner" role="status">
          Showing sample correlation data — weather history API unreachable or empty.
        </div>
      )}

      {isLoading || !history ? (
        <p className="weather-impact-page__loading">Loading weather correlation…</p>
      ) : (
        <>
          <ChartCard title="Weather vs Performance" subtitle={`Rain probability, download speed, and latency · ${PERIOD_LABELS[period]}`}>
            <ResponsiveContainer width="100%" height={320}>
              <ComposedChart data={chartData} margin={{ top: 8, right: 16, left: -8, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" vertical={false} />
                <XAxis dataKey="time" tick={{ fill: "var(--text-muted)", fontSize: 11 }} minTickGap={40} />
                <YAxis
                  yAxisId="speed"
                  tick={{ fill: "var(--text-muted)", fontSize: 11 }}
                  width={44}
                  label={{ value: "Mbps", position: "insideTopLeft", fill: "var(--text-muted)", fontSize: 11 }}
                />
                <YAxis
                  yAxisId="rain"
                  orientation="right"
                  domain={[0, 100]}
                  tick={{ fill: "var(--text-muted)", fontSize: 11 }}
                  width={40}
                  label={{ value: "%", position: "insideTopRight", fill: "var(--text-muted)", fontSize: 11 }}
                />
                <Tooltip content={(props) => <ChartTooltip {...props} />} />
                <Legend wrapperStyle={{ fontSize: 12, color: "var(--text-muted)" }} />
                <Line
                  yAxisId="rain"
                  type="monotone"
                  dataKey="rainChance"
                  name="Rain %"
                  stroke="var(--accent)"
                  strokeWidth={2}
                  dot={false}
                  isAnimationActive={false}
                  connectNulls
                />
                <Line
                  yAxisId="speed"
                  type="monotone"
                  dataKey="downloadMbps"
                  name="Download Mbps"
                  stroke="var(--accent-2)"
                  strokeWidth={2}
                  dot={false}
                  isAnimationActive={false}
                  connectNulls
                />
                <Line
                  yAxisId="speed"
                  type="monotone"
                  dataKey="latencyMs"
                  name="Latency ms"
                  stroke="var(--accent-3)"
                  strokeWidth={2}
                  dot={false}
                  isAnimationActive={false}
                  connectNulls
                />
              </ComposedChart>
            </ResponsiveContainer>
          </ChartCard>

          <ChartCard title="Outage periods" subtitle={`Connection events overlapping ${PERIOD_LABELS[period].toLowerCase()}`}>
            <OutageTimeline
              events={history.outages}
              windowDays={period === "24h" ? 1 : period === "7d" ? 7 : 30}
            />
          </ChartCard>
        </>
      )}
    </div>
  );
}
