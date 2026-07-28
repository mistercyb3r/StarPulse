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
  hardware_version: string | null;
  software_version: string | null;
  gps_valid: boolean | null;
  gps_enabled: boolean | null;
  gps_satellites: number | null;
    azimuth_deg: number | null;
    elevation_deg: number | null;
    latitude: number | null;
    longitude: number | null;
}

export interface StarlinkHistoryResponse {
  samples: TelemetrySample[];
  count: number;
}

export type SummaryPeriod = "24h" | "7d" | "30d";

export interface StarlinkSummaryResponse {
  sample_count: number;
  average_download_bps: number | null;
  average_upload_bps: number | null;
  average_latency_ms: number | null;
  uptime_percent: number | null;
  average_obstruction_percent: number | null;
  peak_download_bps: number | null;
  peak_upload_bps: number | null;
  best_latency_ms: number | null;
  worst_latency_ms: number | null;
  average_power_watts: number | null;
  min_power_watts: number | null;
  max_power_watts: number | null;
  range_start: string | null;
  range_end: string | null;
}

export interface StarlinkHealthResponse {
  health_score: number | null;
  quality_label: string;
  uptime_percent: number | null;
  latency_ms: number | null;
  obstruction_percent: number | null;
  obstruction_impact: string;
  sample_count: number;
  range_start: string | null;
  range_end: string | null;
}

export interface DishInfoResponse {
  connection_state: ConnectionState;
  uptime_seconds: number | null;
  hardware_version: string | null;
  software_version: string | null;
  gps_valid: boolean | null;
  gps_enabled: boolean | null;
  gps_satellites: number | null;
  azimuth_deg: number | null;
  elevation_deg: number | null;
  last_updated: string;
}

export type OutageReason = "disconnected" | "high_packet_loss" | "dish_unavailable" | string;

export interface ConnectionEventResponse {
  id: number;
  start_time: string;
  end_time: string | null;
  duration_seconds: number | null;
  reason: OutageReason;
}

export interface OutageSummaryResponse {
  outages_today: number;
  outages_last_7d: number;
  total_downtime_minutes_last_7d: number;
  events: ConnectionEventResponse[];
}

export type WeatherLocationSource = "dish_gps" | "configured" | null;

export interface WeatherResponse {
  available: boolean;
  temperature_c: number | null;
  feels_like_c: number | null;
  humidity_percent: number | null;
  wind_speed_kph: number | null;
  conditions: string | null;
  latitude: number | null;
  longitude: number | null;
  location_source: WeatherLocationSource;
  fetched_at: string | null;
  message: string | null;
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
