import { useCallback, useEffect, useRef, useState } from "react";
import { getHealth, getStarlinkHistory, getStarlinkStatus, getStarlinkSummary } from "../api/client";
import { generateMockHealth, generateMockHistoryResponse, generateMockStatus, generateMockSummary } from "../api/mockData";
import type { HealthResponse, StarlinkHistoryResponse, StarlinkSummaryResponse, TelemetrySample } from "../api/types";

const DEFAULT_POLL_INTERVAL_MS = 5000;
const HISTORY_LIMIT = 120;
const SUMMARY_WINDOW_MS = 24 * 60 * 60 * 1000;

export interface StarlinkTelemetryState {
  status: TelemetrySample | null;
  history: StarlinkHistoryResponse | null;
  summary: StarlinkSummaryResponse | null;
  health: HealthResponse | null;
  /** True once the very first fetch (real or mock) has completed. */
  isLoading: boolean;
  /** True when showing generated fallback data because the API was unreachable. */
  isUsingMockData: boolean;
  lastUpdated: Date | null;
}

/**
 * Polls the StarPulse API for the latest status, recent history, and a
 * rolling 24h summary. Falls back to generated mock data (all three,
 * together, so the numbers stay internally consistent) whenever any of
 * those requests fail — e.g. the backend isn't running, or it's a fresh
 * install with no telemetry collected yet.
 */
export function useStarlinkTelemetry(pollIntervalMs: number = DEFAULT_POLL_INTERVAL_MS): StarlinkTelemetryState {
  const [state, setState] = useState<StarlinkTelemetryState>({
    status: null,
    history: null,
    summary: null,
    health: null,
    isLoading: true,
    isUsingMockData: false,
    lastUpdated: null,
  });

  const isMountedRef = useRef(true);

  const refresh = useCallback(async () => {
    const summaryRangeStart = new Date(Date.now() - SUMMARY_WINDOW_MS).toISOString();

    try {
      const [status, history, summary, health] = await Promise.all([
        getStarlinkStatus(),
        getStarlinkHistory({ limit: HISTORY_LIMIT }),
        getStarlinkSummary({ start: summaryRangeStart }),
        getHealth(),
      ]);

      if (!isMountedRef.current) return;
      setState({ status, history, summary, health, isLoading: false, isUsingMockData: false, lastUpdated: new Date() });
    } catch {
      if (!isMountedRef.current) return;
      setState({
        status: generateMockStatus(),
        history: generateMockHistoryResponse(HISTORY_LIMIT),
        summary: generateMockSummary(),
        health: generateMockHealth(),
        isLoading: false,
        isUsingMockData: true,
        lastUpdated: new Date(),
      });
    }
  }, []);

  useEffect(() => {
    isMountedRef.current = true;
    void refresh();
    const interval = setInterval(() => void refresh(), pollIntervalMs);
    return () => {
      isMountedRef.current = false;
      clearInterval(interval);
    };
  }, [refresh, pollIntervalMs]);

  return state;
}
