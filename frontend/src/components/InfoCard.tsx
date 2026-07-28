import type { ReactNode } from "react";
import { ChartCard } from "./charts/ChartCard";
import "./InfoCard.css";

export type InfoCardTone = "good" | "warn" | "bad" | "neutral";

export interface InfoCardRow {
  label: string;
  value: string;
  tone?: InfoCardTone;
}

interface InfoCardProps {
  title: string;
  subtitle?: string;
  rows: InfoCardRow[];
  footer?: ReactNode;
  /** Shown instead of the rows/footer when there's a reason data can't be displayed (e.g. weather disabled). */
  unavailableMessage?: string | null;
}

/**
 * A small "label: value" list card matching the dashboard's existing
 * style (used for Power, Latency, and Connection History) — reuses
 * `ChartCard` for the outer frame so new cards stay visually consistent
 * without duplicating that chrome.
 */
export function InfoCard({ title, subtitle, rows, footer, unavailableMessage }: InfoCardProps) {
  return (
    <ChartCard title={title} subtitle={subtitle}>
      {unavailableMessage ? (
        <p className="info-card__unavailable">{unavailableMessage}</p>
      ) : (
        <>
          <dl className="info-card">
            {rows.map((row) => (
              <div className="info-card__row" key={row.label}>
                <dt className="info-card__label">{row.label}</dt>
                <dd className={`info-card__value info-card__value--${row.tone ?? "neutral"}`}>{row.value}</dd>
              </div>
            ))}
          </dl>
          {footer && <div className="info-card__footer">{footer}</div>}
        </>
      )}
    </ChartCard>
  );
}
