import type { ReactNode } from "react";
import "./ChartTooltip.css";

interface TooltipPayloadEntry {
  name?: ReactNode;
  value?: number | string | readonly (number | string)[];
  color?: string;
  dataKey?: unknown;
}

interface ChartTooltipProps {
  active?: boolean;
  label?: string | number;
  payload?: readonly TooltipPayloadEntry[];
  unit?: string;
}

/** A recharts-compatible custom tooltip with StarPulse's dark styling. */
export function ChartTooltip({ active, payload, label, unit = "" }: ChartTooltipProps) {
  if (!active || !payload || payload.length === 0) return null;

  return (
    <div className="chart-tooltip">
      <div className="chart-tooltip__label">{label}</div>
      {payload.map((entry, index) => (
        <div key={index} className="chart-tooltip__row">
          <span className="chart-tooltip__swatch" style={{ background: entry.color }} />
          <span className="chart-tooltip__name">{entry.name}</span>
          <span className="chart-tooltip__value">
            {typeof entry.value === "number" ? entry.value.toFixed(1) : String(entry.value ?? "")}
            {unit}
          </span>
        </div>
      ))}
    </div>
  );
}
