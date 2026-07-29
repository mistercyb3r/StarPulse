import type { WeatherImpactResponse } from "../api/types";
import { formatBps, formatMs } from "../utils/format";
import { ChartCard } from "./charts/ChartCard";
import "./SignalConditionsCard.css";

interface SignalConditionsCardProps {
  impact: WeatherImpactResponse | null;
}

type Tone = "good" | "warn" | "bad" | "neutral";

function toneForSeverity(severity: string | undefined): Tone {
  if (severity === "Low") return "good";
  if (severity === "Moderate") return "warn";
  if (severity === "High") return "bad";
  return "neutral";
}

export function SignalConditionsCard({ impact }: SignalConditionsCardProps) {
  if (impact === null) {
    return (
      <ChartCard title="📡 Signal" subtitle="Weather impact on Starlink performance">
        <p className="signal-conditions__empty">Loading signal conditions…</p>
      </ChartCard>
    );
  }

  if (!impact.available) {
    return (
      <ChartCard title="📡 Signal" subtitle="Weather impact on Starlink performance">
        <p className="signal-conditions__empty">{impact.message ?? "Signal conditions unavailable"}</p>
      </ChartCard>
    );
  }

  const tone = toneForSeverity(impact.severity);

  return (
    <ChartCard title="📡 Signal" subtitle="Weather impact on Starlink performance">
      <div className="signal-conditions">
        <div className="signal-conditions__impact">
          <span className="signal-conditions__label">Weather impact</span>
          <span className={`signal-conditions__severity signal-conditions__severity--${tone}`}>{impact.severity}</span>
        </div>
        <div className="signal-conditions__metrics">
          <div>
            <span className="signal-conditions__label">Latency</span>
            <span className="signal-conditions__value">{formatMs(impact.latency_ms)}</span>
          </div>
          <div>
            <span className="signal-conditions__label">Speed</span>
            <span className="signal-conditions__value">{formatBps(impact.download_bps)}</span>
          </div>
        </div>
        {impact.reasons.length > 0 && (
          <ul className="signal-conditions__reasons">
            {impact.reasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        )}
      </div>
    </ChartCard>
  );
}
