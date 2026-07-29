import { useEffect, useState } from "react";
import { getAbout } from "../api/client";
import type { AboutResponse } from "../api/types";
import { BrandMark } from "./BrandMark";
import "./AboutPage.css";

interface AboutPageProps {
  onBack: () => void;
}

function formatUptime(seconds: number): string {
  const total = Math.max(0, Math.floor(seconds));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

export function AboutPage({ onBack }: AboutPageProps) {
  const [about, setAbout] = useState<AboutResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getAbout()
      .then((data) => {
        if (!cancelled) setAbout(data);
      })
      .catch(() => {
        if (!cancelled) setError("Could not load system information.");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="about-page">
      <header className="about-page__header">
        <button type="button" className="about-page__back" onClick={onBack}>
          ← Dashboard
        </button>
        <BrandMark size={48} version={about?.version ?? "1.0"} />
      </header>

      {error && <p className="about-page__error">{error}</p>}

      <section className="about-page__card">
        <h2>About StarPulse</h2>
        <p>{about?.description ?? "Self-hosted local Starlink telemetry dashboard."}</p>
        <dl className="about-page__dl">
          <div>
            <dt>Version</dt>
            <dd>{about?.version ?? "—"}</dd>
          </div>
          <div>
            <dt>GitHub</dt>
            <dd>
              {about ? (
                <a href={about.github_url} target="_blank" rel="noreferrer">
                  {about.github_url}
                </a>
              ) : (
                "—"
              )}
            </dd>
          </div>
        </dl>
      </section>

      <section className="about-page__card">
        <h2>🖥️ System information</h2>
        <dl className="about-page__dl">
          <div>
            <dt>Uptime</dt>
            <dd>{about ? formatUptime(about.uptime_seconds) : "—"}</dd>
          </div>
          <div>
            <dt>Setup complete</dt>
            <dd>{about ? (about.setup_complete ? "Yes" : "No") : "—"}</dd>
          </div>
          <div>
            <dt>Dish connected</dt>
            <dd>
              {about?.starlink_connected == null ? "Unknown" : about.starlink_connected ? "Yes" : "No"}
            </dd>
          </div>
          <div>
            <dt>Platform</dt>
            <dd>{about?.platform ?? "—"}</dd>
          </div>
          <div>
            <dt>Python</dt>
            <dd>{about?.python_version ?? "—"}</dd>
          </div>
          <div>
            <dt>Data directory</dt>
            <dd className="about-page__mono">{about?.data_dir ?? "—"}</dd>
          </div>
          <div>
            <dt>Database</dt>
            <dd className="about-page__mono">{about?.database_path ?? "—"}</dd>
          </div>
        </dl>
      </section>

      <section className="about-page__card">
        <h2>Credits</h2>
        <ul className="about-page__credits">
          {(about?.credits ?? ["Built for self-hosted Starlink monitoring."]).map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
      </section>
    </div>
  );
}
