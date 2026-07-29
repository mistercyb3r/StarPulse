import type { CSSProperties, ReactNode } from "react";
import "./BrandMark.css";

interface BrandMarkProps {
  size?: number;
  withWordmark?: boolean;
  version?: string;
  className?: string;
}

export function BrandMark({ size = 36, withWordmark = true, version, className }: BrandMarkProps) {
  const style = { "--brand-size": `${size}px` } as CSSProperties;
  return (
    <div className={`brand-mark ${className ?? ""}`.trim()} style={style}>
      <img className="brand-mark__logo" src="/logo.svg" width={size} height={size} alt="" aria-hidden="true" />
      {withWordmark && (
        <div className="brand-mark__text">
          <span className="brand-mark__name">StarPulse</span>
          {version && <span className="brand-mark__version">v{version}</span>}
        </div>
      )}
    </div>
  );
}

interface TooltipProps {
  text: string;
  children: ReactNode;
}

export function Tooltip({ text, children }: TooltipProps) {
  return (
    <span className="sp-tooltip" title={text} data-tooltip={text}>
      {children}
    </span>
  );
}
