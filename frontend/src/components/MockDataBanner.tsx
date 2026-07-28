import "./MockDataBanner.css";

export function MockDataBanner() {
  return (
    <div className="mock-banner" role="status">
      <span className="mock-banner__dot" aria-hidden="true" />
      Showing sample data — the StarPulse API is unreachable or has no telemetry recorded yet.
    </div>
  );
}
