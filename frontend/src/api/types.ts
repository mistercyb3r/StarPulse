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
  altitude_m?: number | null;
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

export type WeatherLocationSource = "configured" | "geoip" | "dish_gps" | "stored" | null;

export interface LocationResponse {
  available: boolean;
  latitude: number | null;
  longitude: number | null;
  altitude_m: number | null;
  source: WeatherLocationSource;
  source_label: string | null;
  place_name: string | null;
  accuracy: string | null;
  approximate: boolean;
  gps_valid: boolean | null;
  gps_enabled: boolean | null;
  gps_satellites: number | null;
  coordinates_collected: boolean;
  message: string | null;
}

export interface LocationSettingsResponse {
  active_source: WeatherLocationSource;
  active_source_label: string | null;
  active_latitude: number | null;
  active_longitude: number | null;
  place_name: string | null;
  accuracy: string | null;
  approximate: boolean;
  weather_ok: boolean;
  weather_summary: string | null;
  dish_gps_available: boolean;
  dish_latitude: number | null;
  dish_longitude: number | null;
  manual_latitude: number | null;
  manual_longitude: number | null;
  gps_valid: boolean | null;
  gps_enabled: boolean | null;
  gps_satellites: number | null;
  advanced_note: string | null;
  message: string | null;
  privacy_note: string;
}

export interface ManualLocationRequest {
  latitude: number;
  longitude: number;
}

export interface LocationActionResponse {
  ok: boolean;
  message: string;
  settings: LocationSettingsResponse;
}

export interface WeatherResponse {
  available: boolean;
  temperature_c: number | null;
  feels_like_c: number | null;
  humidity_percent: number | null;
  wind_speed_kph: number | null;
  conditions: string | null;
  precipitation_mm: number | null;
  precipitation_probability: number | null;
  latitude: number | null;
  longitude: number | null;
  location_source: WeatherLocationSource;
  fetched_at: string | null;
  message: string | null;
}

export type WeatherImpactSeverity = "Low" | "Moderate" | "High" | "Unknown" | string;

export interface WeatherImpactResponse {
  available: boolean;
  severity: WeatherImpactSeverity;
  reasons: string[];
  conditions: string | null;
  temperature_c: number | null;
  wind_speed_kph: number | null;
  precipitation_probability: number | null;
  precipitation_mm: number | null;
  latency_ms: number | null;
  download_bps: number | null;
  upload_bps: number | null;
  latency_delta_percent: number | null;
  download_delta_percent: number | null;
  active_outage: boolean;
  sample_count: number;
  message: string | null;
}

export type WeatherHistoryPeriod = "24h" | "7d" | "30d";

export interface WeatherHistoryPoint {
  timestamp: string;
  temperature_c: number | null;
  wind_speed_kph: number | null;
  precipitation_mm: number | null;
  precipitation_probability: number | null;
  conditions: string | null;
}

export interface PerformanceBucket {
  timestamp: string;
  average_download_bps: number | null;
  average_upload_bps: number | null;
  average_latency_ms: number | null;
  sample_count: number;
}

export interface WeatherHistoryResponse {
  period: WeatherHistoryPeriod;
  range_start: string;
  range_end: string;
  weather: WeatherHistoryPoint[];
  performance: PerformanceBucket[];
  outages: ConnectionEventResponse[];
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
  weather_latitude: number | null;
  weather_longitude: number | null;
}

export interface SetupRequest {
  dish_host: string;
  poll_interval_seconds: number;
  port: number;
  weather_latitude?: number | null;
  weather_longitude?: number | null;
}

export interface SetupResponse {
  setup_complete: boolean;
  restart_required: boolean;
  message: string;
}

export interface NotificationSettingsResponse {
  enabled: boolean;
  smtp_host: string;
  smtp_port: number;
  smtp_user: string;
  smtp_password_set: boolean;
  smtp_from: string;
  smtp_to: string;
  smtp_use_tls: boolean;
  cooldown_seconds: number;
  latency_warn_ms: number;
  packet_loss_warn: number;
  obstruction_warn_percent: number;
  health_warn_score: number;
  smtp_configured: boolean;
}

export interface NotificationSettingsUpdate {
  enabled?: boolean;
  smtp_host?: string;
  smtp_port?: number;
  smtp_user?: string;
  smtp_password?: string;
  smtp_from?: string;
  smtp_to?: string;
  smtp_use_tls?: boolean;
  cooldown_seconds?: number;
  latency_warn_ms?: number;
  packet_loss_warn?: number;
  obstruction_warn_percent?: number;
  health_warn_score?: number;
}

export interface NotificationSettingsActionResponse {
  ok: boolean;
  message: string;
  settings: NotificationSettingsResponse;
}

export interface NotificationTestResponse {
  ok: boolean;
  status: string;
  message: string;
  event_id: number | null;
}

export interface NotificationHistoryItem {
  id: number;
  timestamp: string;
  event_type: string;
  channel: string;
  subject: string;
  body: string;
  status: string;
  error_message: string | null;
}

export interface NotificationHistoryResponse {
  events: NotificationHistoryItem[];
  count: number;
}

export interface AboutResponse {
  name: string;
  version: string;
  description: string;
  github_url: string;
  uptime_seconds: number;
  setup_complete: boolean;
  starlink_connected: boolean | null;
  database_path: string;
  data_dir: string;
  python_version: string;
  platform: string;
  credits: string[];
}
