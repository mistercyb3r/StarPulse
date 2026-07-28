import type { ConnectionEventResponse } from "../../api/types";
import { formatClockTime } from "../../utils/format";
import "./OutageTimeline.css";

interface OutageTimelineProps {
  events: ConnectionEventResponse[];
  windowDays?: number;
}

const REASON_LABELS: Record<string, string> = {
  disconnected: "Disconnected",
  high_packet_loss: "High Packet Loss",
  dish_unavailable: "Dish Unavailable",
};

type ReasonTone = "bad" | "warn" | "unavailable";

function reasonTone(reason: string): ReasonTone {
  if (reason === "high_packet_loss") return "warn";
  if (reason === "dish_unavailable") return "unavailable";
  return "bad";
}

/** A 7-day horizontal timeline of degraded-connection events, positioned proportionally by time. */
export function OutageTimeline({ events, windowDays = 7 }: OutageTimelineProps) {
  const now = Date.now();
  const windowStart = now - windowDays * 24 * 60 * 60 * 1000;
  const span = now - windowStart;

  return (
    <div className="outage-timeline">
      <div className="outage-timeline__track">
        {events.length === 0 ? (
          <span className="outage-timeline__empty">No outages in the last {windowDays} days</span>
        ) : (
          events.map((event) => {
            const start = new Date(event.start_time).getTime();
            const end = event.end_time ? new Date(event.end_time).getTime() : now;
            const left = Math.min(100, Math.max(0, ((start - windowStart) / span) * 100));
            const width = Math.min(100 - left, Math.max(0.6, ((end - start) / span) * 100));
            const tone = reasonTone(event.reason);

            return (
              <span
                key={event.id}
                className={`outage-timeline__segment outage-timeline__segment--${tone}`}
                style={{ left: `${left}%`, width: `${width}%` }}
                title={`${REASON_LABELS[event.reason] ?? event.reason} — started ${formatClockTime(event.start_time)}`}
              />
            );
          })
        )}
      </div>
      <div className="outage-timeline__axis">
        <span>{windowDays}d ago</span>
        <span>Now</span>
      </div>
      <div className="outage-timeline__legend">
        <LegendItem tone="bad" label="Disconnected" />
        <LegendItem tone="warn" label="High Packet Loss" />
        <LegendItem tone="unavailable" label="Dish Unavailable" />
      </div>
    </div>
  );
}

function LegendItem({ tone, label }: { tone: ReasonTone; label: string }) {
  return (
    <span className="outage-timeline__legend-item">
      <span className={`outage-timeline__legend-swatch outage-timeline__legend-swatch--${tone}`} />
      {label}
    </span>
  );
}
