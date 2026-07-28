import type { ConnectionState, TelemetrySample } from "../../api/types";
import { formatClockTime } from "../../utils/format";
import { ChartCard } from "./ChartCard";
import "./ConnectionTimeline.css";

interface ConnectionTimelineProps {
  samples: TelemetrySample[];
}

type Tone = "good" | "warn" | "bad";

function toneForState(state: ConnectionState): Tone {
  if (state === "CONNECTED") return "good";
  if (state === "SEARCHING" || state === "UNKNOWN") return "warn";
  return "bad";
}

export function ConnectionTimeline({ samples }: ConnectionTimelineProps) {
  return (
    <ChartCard title="Connection State Timeline" subtitle="One bar per sample, oldest to newest">
      {samples.length === 0 ? (
        <p className="connection-timeline__empty">No samples yet.</p>
      ) : (
        <div className="connection-timeline">
          {samples.map((sample) => (
            <div
              key={sample.id}
              className={`connection-timeline__bar connection-timeline__bar--${toneForState(sample.connection_state)}`}
              title={`${formatClockTime(sample.timestamp)} — ${sample.connection_state}`}
            />
          ))}
        </div>
      )}
      <div className="connection-timeline__legend">
        <LegendItem tone="good" label="Connected" />
        <LegendItem tone="warn" label="Searching / Unknown" />
        <LegendItem tone="bad" label="Offline / Obstructed" />
      </div>
    </ChartCard>
  );
}

function LegendItem({ tone, label }: { tone: Tone; label: string }) {
  return (
    <span className="connection-timeline__legend-item">
      <span className={`connection-timeline__legend-swatch connection-timeline__legend-swatch--${tone}`} />
      {label}
    </span>
  );
}
