/**
 * Mirrors the Pydantic response models in `starpulse.api.schemas`
 * (backend: src/starpulse/api/schemas.py). Keep in sync by hand for now
 * — there's no shared schema generation yet.
 */

export type ConnectionState = "CONNECTED" | "SEARCHING" | "UNKNOWN" | string;

export interface TelemetrySample {
  id: number;
  timestamp: string;
  connection_state: ConnectionState;
  uptime_seconds: number | null;
  download_bps: number | null;
  upload_bps: number | null;
  latency_ms: number | null;
  ping_drop_rate: number | null;
  obstruction_percent: number | null;
  currently_obstructed: boolean | null;
  snr: number | null;
  power_watts: number | null;
}

export interface StarlinkHistoryResponse {
  samples: TelemetrySample[];
  count: number;
}

export interface StarlinkSummaryResponse {
  sample_count: number;
  average_download_bps: number | null;
  average_upload_bps: number | null;
  average_latency_ms: number | null;
  uptime_percent: number | null;
  average_obstruction_percent: number | null;
  range_start: string | null;
  range_end: string | null;
}

export interface HealthResponse {
  status: string;
  version: string;
  uptime_seconds: number;
  setup_complete: boolean;
  /** Null until the collector has attempted at least one poll. */
  starlink_connected: boolean | null;
}

export interface SetupStatusResponse {
  setup_complete: boolean;
  dish_host: string;
  dish_port: number;
  poll_interval_seconds: number;
  port: number;
}

export interface SetupRequest {
  dish_host: string;
  poll_interval_seconds: number;
  port: number;
}

export interface SetupResponse {
  setup_complete: boolean;
  restart_required: boolean;
  message: string;
}
