import type { ConnectionState } from "../api/types";
import "./StatusBadge.css";

interface StatusMeta {
  label: string;
  tone: "good" | "warn" | "bad";
}

function describeState(state: ConnectionState): StatusMeta {
  switch (state) {
    case "CONNECTED":
      return { label: "Connected", tone: "good" };
    case "SEARCHING":
      return { label: "Searching", tone: "warn" };
    case "UNKNOWN":
      return { label: "Unknown", tone: "warn" };
    default:
      return { label: state.replaceAll("_", " ").toLowerCase(), tone: "bad" };
  }
}

export function StatusBadge({ state }: { state: ConnectionState }) {
  const { label, tone } = describeState(state);
  return (
    <span className={`status-badge status-badge--${tone}`}>
      <span className="status-badge__dot" aria-hidden="true" />
      <span className="status-badge__label">{label}</span>
    </span>
  );
}
