import type { ReactNode } from "react";
import "./MetricCard.css";

export type MetricTone = "good" | "warn" | "bad" | "neutral";

interface MetricCardProps {
  label: string;
  value: string;
  sublabel?: string;
  tone?: MetricTone;
  icon?: ReactNode;
}

export function MetricCard({ label, value, sublabel, tone = "neutral", icon }: MetricCardProps) {
  return (
    <div className={`metric-card metric-card--${tone}`}>
      <div className="metric-card__header">
        <span className="metric-card__label">{label}</span>
        {icon && <span className="metric-card__icon">{icon}</span>}
      </div>
      <div className="metric-card__value">{value}</div>
      {sublabel && <div className="metric-card__sublabel">{sublabel}</div>}
    </div>
  );
}
