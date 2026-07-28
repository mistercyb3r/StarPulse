import { useCallback, useEffect, useRef, useState } from "react";
import { getDishInfo, getHealth, getStarlinkHealth, getStarlinkHistory, getStarlinkStatus, getStarlinkSummary } from "../api/client";
import {
  generateMockDishInfo,
  generateMockHealth,
  generateMockHistoryResponse,
  generateMockStarlinkHealth,
  generateMockStatus,
  generateMockSummary,
} from "../api/mockData";
import type {
  DishInfoResponse,
  HealthResponse,
  StarlinkHealthResponse,
  StarlinkHistoryResponse,
  StarlinkSummaryResponse,
  SummaryPeriod,
  TelemetrySample,
} from "../api/types";

const DEFAULT_POLL_INTERVAL_MS = 5000;
const HISTORY_LIMIT = 120;
const DEFAULT_PERFORMANCE_PERIOD: SummaryPeriod = "24h";

export interface StarlinkTelemetryState {
  status: TelemetrySample | null;
  history: StarlinkHistoryResponse | null;
  health: HealthResponse | null;
  /** Connection quality score (0-100) derived from recent uptime/latency/obstruction. */
  starlinkHealth: StarlinkHealthResponse | null;
  dishInfo: DishInfoResponse | null;
  /** Average/peak throughput over the selected `performancePeriod`. */
  performance: StarlinkSummaryResponse | null;
  performancePeriod: SummaryPeriod;
  setPerformancePeriod: (period: SummaryPeriod) => void;
  /** True once the very first fetch (real or mock) has completed. */
  isLoading: boolean;
  /** True when showing generated fallback data because the API was unreachable. */
  isUsingMockData: boolean;
  lastUpdated: Date | null;
}

/**
 * Polls the StarPulse API for the latest status, recent history, connection
 * health score, dish info, and period-selectable performance stats. Falls
 * back to generated mock data (all of it together, so the numbers stay
 * internally consistent) whenever any of those requests fail — e.g. the
 * backend isn't running, or it's a fresh install with no telemetry
 * collected yet.
 */
export function useStarlinkTelemetry(pollIntervalMs: number = DEFAULT_POLL_INTERVAL_MS): StarlinkTelemetryState {
  const [performancePeriod, setPerformancePeriod] = useState<SummaryPeriod>(DEFAULT_PERFORMANCE_PERIOD);
  const [state, setState] = useState<
    Omit<StarlinkTelemetryState, "performancePeriod" | "setPerformancePeriod">
  >({
    status: null,
    history: null,
    health: null,
    starlinkHealth: null,
    dishInfo: null,
    performance: null,
    isLoading: true,
    isUsingMockData: false,
    lastUpdated: null,
  });

  const isMountedRef = useRef(true);

  const refresh = useCallback(async () => {
    try {
      const [status, history, health, starlinkHealth, dishInfo, performance] = await Promise.all([
        getStarlinkStatus(),
        getStarlinkHistory({ limit: HISTORY_LIMIT }),
        getHealth(),
        getStarlinkHealth(),
        getDishInfo(),
        getStarlinkSummary({ period: performancePeriod }),
      ]);

      if (!isMountedRef.current) return;
      setState({
        status,
        history,
        health,
        starlinkHealth,
        dishInfo,
        performance,
        isLoading: false,
        isUsingMockData: false,
        lastUpdated: new Date(),
      });
    } catch {
      if (!isMountedRef.current) return;
      setState({
        status: generateMockStatus(),
        history: generateMockHistoryResponse(HISTORY_LIMIT),
        health: generateMockHealth(),
        starlinkHealth: generateMockStarlinkHealth(),
        dishInfo: generateMockDishInfo(),
        performance: generateMockSummary(performancePeriod),
        isLoading: false,
        isUsingMockData: true,
        lastUpdated: new Date(),
      });
    }
  }, [performancePeriod]);

  useEffect(() => {
    isMountedRef.current = true;
    void refresh();
    const interval = setInterval(() => void refresh(), pollIntervalMs);
    return () => {
      isMountedRef.current = false;
      clearInterval(interval);
    };
  }, [refresh, pollIntervalMs]);

  return { ...state, performancePeriod, setPerformancePeriod };
}
