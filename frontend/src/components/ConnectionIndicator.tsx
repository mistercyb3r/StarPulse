import "./StatusBadge.css";

type Tone = "good" | "warn" | "bad";

interface ConnectionIndicatorProps {
  label: string;
  tone: Tone;
}

/** Same visual style as StatusBadge, for indicators that aren't a dish connection state. */
export function ConnectionIndicator({ label, tone }: ConnectionIndicatorProps) {
  return (
    <span className={`status-badge status-badge--${tone}`}>
      <span className="status-badge__dot" aria-hidden="true" />
      <span className="status-badge__label">{label}</span>
    </span>
  );
}
