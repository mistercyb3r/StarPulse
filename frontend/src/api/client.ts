import type {
  HealthResponse,
  SetupRequest,
  SetupResponse,
  SetupStatusResponse,
  StarlinkHistoryResponse,
  StarlinkSummaryResponse,
  TelemetrySample,
} from "./types";

// Empty string = relative paths, which work with the Vite dev proxy
// (see vite.config.ts) or a same-origin reverse proxy in production.
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

const REQUEST_TIMEOUT_MS = 5000;

/** Thrown for any failure to reach or parse a response from the API. */
export class ApiUnavailableError extends Error {}

function buildUrl(path: string, params?: Record<string, string | number | undefined>): string {
  const searchParams = new URLSearchParams();
  for (const [key, value] of Object.entries(params ?? {})) {
    if (value !== undefined) {
      searchParams.set(key, String(value));
    }
  }
  const query = searchParams.toString();
  return `${API_BASE_URL}${path}${query ? `?${query}` : ""}`;
}

async function getJson<T>(path: string, params?: Record<string, string | number | undefined>): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  let response: Response;
  try {
    response = await fetch(buildUrl(path, params), {
      signal: controller.signal,
      headers: { Accept: "application/json" },
    });
  } catch (cause) {
    throw new ApiUnavailableError(`Could not reach StarPulse API at ${path}`, { cause });
  } finally {
    clearTimeout(timeout);
  }

  if (!response.ok) {
    throw new ApiUnavailableError(`StarPulse API returned ${response.status} for ${path}`);
  }

  try {
    return (await response.json()) as T;
  } catch (cause) {
    throw new ApiUnavailableError(`StarPulse API returned invalid JSON for ${path}`, { cause });
  }
}

/** Thrown for 4xx responses, so callers (the setup form) can show the validation message. */
export class ApiValidationError extends Error {
  constructor(
    message: string,
    public readonly detail: unknown,
  ) {
    super(message);
  }
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  let response: Response;
  try {
    response = await fetch(buildUrl(path), {
      method: "POST",
      signal: controller.signal,
      headers: { Accept: "application/json", "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch (cause) {
    throw new ApiUnavailableError(`Could not reach StarPulse API at ${path}`, { cause });
  } finally {
    clearTimeout(timeout);
  }

  if (response.status >= 400 && response.status < 500) {
    const detail = await response.json().catch(() => null);
    throw new ApiValidationError(`StarPulse API rejected the request to ${path}`, detail);
  }
  if (!response.ok) {
    throw new ApiUnavailableError(`StarPulse API returned ${response.status} for ${path}`);
  }

  try {
    return (await response.json()) as T;
  } catch (cause) {
    throw new ApiUnavailableError(`StarPulse API returned invalid JSON for ${path}`, { cause });
  }
}

export function getHealth(): Promise<HealthResponse> {
  return getJson<HealthResponse>("/api/health");
}

export function getSetupStatus(): Promise<SetupStatusResponse> {
  return getJson<SetupStatusResponse>("/api/setup/status");
}

export function submitSetup(payload: SetupRequest): Promise<SetupResponse> {
  return postJson<SetupResponse>("/api/setup", payload);
}

export function getStarlinkStatus(): Promise<TelemetrySample> {
  return getJson<TelemetrySample>("/api/starlink/status");
}

export interface HistoryParams {
  start?: string;
  end?: string;
  limit?: number;
  [key: string]: string | number | undefined;
}

export function getStarlinkHistory(params: HistoryParams = {}): Promise<StarlinkHistoryResponse> {
  return getJson<StarlinkHistoryResponse>("/api/starlink/history", params);
}

export interface SummaryParams {
  start?: string;
  end?: string;
  [key: string]: string | number | undefined;
}

export function getStarlinkSummary(params: SummaryParams = {}): Promise<StarlinkSummaryResponse> {
  return getJson<StarlinkSummaryResponse>("/api/starlink/summary", params);
}
