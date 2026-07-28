import type {
  DishInfoResponse,
  HealthResponse,
  StarlinkHealthResponse,
  StarlinkHistoryResponse,
  StarlinkSummaryResponse,
  SummaryPeriod,
  TelemetrySample,
} from "./types";

/**
 * Deterministic-ish sample data shown when the StarPulse API can't be
 * reached, so the dashboard is still useful to look at (e.g. while
 * developing the frontend without a backend running, or on a fresh
 * install before the collector has gathered any real samples).
 */

const SAMPLE_INTERVAL_MS = 5000;
const HISTORY_LENGTH = 120; // ~10 minutes at the default 5s poll interval

function pseudoRandom(seed: number): number {
  const x = Math.sin(seed) * 10000;
  return x - Math.floor(x);
}

function buildSample(index: number, timestamp: Date): TelemetrySample {
  const wobble = pseudoRandom(index);
  const isBriefOutage = index > 0 && index % 47 === 0;

  return {
    id: index,
    timestamp: timestamp.toISOString(),
    connection_state: isBriefOutage ? "SEARCHING" : "CONNECTED",
    uptime_seconds: 3 * 24 * 3600 + index * 5,
    download_bps: isBriefOutage ? 0 : Math.round((150 + wobble * 40 - 20) * 1_000_000),
    upload_bps: isBriefOutage ? 0 : Math.round((14 + wobble * 6 - 3) * 1_000_000),
    latency_ms: isBriefOutage ? null : Math.round((28 + wobble * 20 - 10) * 10) / 10,
    ping_drop_rate: isBriefOutage ? 1 : Math.round(wobble * 2) / 100,
    obstruction_percent: Math.round(wobble * 30) / 100,
    currently_obstructed: wobble > 0.97,
    snr: null,
    power_watts: Math.round((38 + wobble * 8 - 4) * 10) / 10,
    hardware_version: "rev3_prod2400",
    software_version: "2026.01.01.mr1",
    gps_valid: true,
    gps_enabled: true,
    gps_satellites: 14 + Math.round(wobble * 4),
    azimuth_deg: Math.round((172 + wobble * 4) * 10) / 10,
    elevation_deg: Math.round((59 + wobble * 4) * 10) / 10,
  };
}

export function generateMockHistory(length: number = HISTORY_LENGTH): TelemetrySample[] {
  const now = Date.now();
  const samples: TelemetrySample[] = [];
  for (let i = 0; i < length; i++) {
    const timestamp = new Date(now - (length - 1 - i) * SAMPLE_INTERVAL_MS);
    samples.push(buildSample(i, timestamp));
  }
  return samples;
}

export function generateMockStatus(): TelemetrySample {
  const history = generateMockHistory(1);
  return { ...history[0], id: 0, timestamp: new Date().toISOString(), connection_state: "CONNECTED" };
}

export function generateMockHistoryResponse(limit: number = HISTORY_LENGTH): StarlinkHistoryResponse {
  const samples = generateMockHistory(limit);
  return { samples, count: samples.length };
}

export function generateMockHealth(): HealthResponse {
  return {
    status: "ok",
    version: "0.0.0-mock",
    uptime_seconds: 3600,
    setup_complete: true,
    starlink_connected: true,
  };
}

const PERIOD_LENGTHS: Record<SummaryPeriod, number> = {
  "24h": 288, // 5-minute-equivalent resolution for a day's worth of mock samples
  "7d": 504,
  "30d": 720,
};

export function generateMockSummary(period: SummaryPeriod = "24h"): StarlinkSummaryResponse {
  const samples = generateMockHistory(PERIOD_LENGTHS[period]);
  const numeric = (values: Array<number | null>) => values.filter((v): v is number => v !== null);

  const average = (values: number[]) => (values.length === 0 ? null : values.reduce((a, b) => a + b, 0) / values.length);
  const peak = (values: number[]) => (values.length === 0 ? null : Math.max(...values));

  const connectedCount = samples.filter((s) => s.connection_state === "CONNECTED").length;
  const downloadValues = numeric(samples.map((s) => s.download_bps));
  const uploadValues = numeric(samples.map((s) => s.upload_bps));

  return {
    sample_count: samples.length,
    average_download_bps: average(downloadValues),
    average_upload_bps: average(uploadValues),
    average_latency_ms: average(numeric(samples.map((s) => s.latency_ms))),
    uptime_percent: (connectedCount / samples.length) * 100,
    average_obstruction_percent: average(numeric(samples.map((s) => s.obstruction_percent))),
    peak_download_bps: peak(downloadValues),
    peak_upload_bps: peak(uploadValues),
    range_start: samples[0]?.timestamp ?? null,
    range_end: samples[samples.length - 1]?.timestamp ?? null,
  };
}

/** Mock for the Starlink connection health score (distinct from `generateMockHealth`, the app/API health). */
export function generateMockStarlinkHealth(): StarlinkHealthResponse {
  return {
    health_score: 96,
    quality_label: "Excellent",
    uptime_percent: 99.6,
    latency_ms: 26.5,
    obstruction_percent: 0.4,
    obstruction_impact: "None",
    sample_count: 12,
    range_start: new Date(Date.now() - 60 * 60 * 1000).toISOString(),
    range_end: new Date().toISOString(),
  };
}

export function generateMockDishInfo(): DishInfoResponse {
  const sample = generateMockStatus();
  return {
    connection_state: sample.connection_state,
    uptime_seconds: sample.uptime_seconds,
    hardware_version: sample.hardware_version,
    software_version: sample.software_version,
    gps_valid: sample.gps_valid,
    gps_enabled: sample.gps_enabled,
    gps_satellites: sample.gps_satellites,
    azimuth_deg: sample.azimuth_deg,
    elevation_deg: sample.elevation_deg,
    last_updated: sample.timestamp,
  };
}
