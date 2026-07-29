import type { StarlinkHealthResponse } from "../api/types";
import { formatMs, formatPercent } from "../utils/format";
import "./StarlinkHealthCard.css";

type Tone = "good" | "warn" | "bad" | "neutral";

function toneForQuality(label: string): Tone {
  if (label === "Excellent" || label === "Good") return "good";
  if (label === "Fair") return "warn";
  if (label === "Poor" || label === "Critical") return "bad";
  return "neutral";
}

interface StarlinkHealthCardProps {
  health: StarlinkHealthResponse | null;
}

export function StarlinkHealthCard({ health }: StarlinkHealthCardProps) {
  const tone: Tone = health ? toneForQuality(health.quality_label) : "neutral";
  const score = health?.health_score;
  const scoreDisplay = score == null ? "—" : Math.round(score);

  return (
    <section className={`health-card health-card--${tone}`}>
      <div className="health-card__ring" style={{ "--score": score ?? 0 } as React.CSSProperties}>
        <div className="health-card__ring-inner">
          <span className="health-card__score">{scoreDisplay}</span>
          <span className="health-card__score-max">/ 100</span>
        </div>
      </div>

      <div className="health-card__body">
        <div className="health-card__heading">
          <span className="health-card__label">🛰️ Starlink Health</span>
          <span className={`health-card__quality health-card__quality--${tone}`}>{health?.quality_label ?? "Unknown"}</span>
        </div>

        <div className="health-card__stats">
          <div className="health-card__stat">
            <span className="health-card__stat-label">Uptime</span>
            <span className="health-card__stat-value">{formatPercent(health?.uptime_percent)}</span>
          </div>
          <div className="health-card__stat">
            <span className="health-card__stat-label">Latency</span>
            <span className="health-card__stat-value">{formatMs(health?.latency_ms)}</span>
          </div>
          <div className="health-card__stat">
            <span className="health-card__stat-label">Obstruction Impact</span>
            <span className="health-card__stat-value">{health?.obstruction_impact ?? "Unknown"}</span>
          </div>
        </div>
      </div>
    </section>
  );
}
