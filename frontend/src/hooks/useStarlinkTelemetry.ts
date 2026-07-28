import { useCallback, useEffect, useRef, useState } from "react";
import {
  getDishInfo,
  getHealth,
  getLocation,
  getOutages,
  getStarlinkHealth,
  getStarlinkHistory,
  getStarlinkStatus,
  getStarlinkSummary,
  getWeather,
  getWeatherImpact,
} from "../api/client";
import {
  generateMockDishInfo,
  generateMockHealth,
  generateMockHistoryResponse,
  generateMockLocation,
  generateMockOutageSummary,
  generateMockStarlinkHealth,
  generateMockStatus,
  generateMockSummary,
  generateMockWeather,
  generateMockWeatherImpact,
} from "../api/mockData";
import type {
  DishInfoResponse,
  HealthResponse,
  LocationResponse,
  OutageSummaryResponse,
  StarlinkHealthResponse,
  StarlinkHistoryResponse,
  StarlinkSummaryResponse,
  SummaryPeriod,
  TelemetrySample,
  WeatherImpactResponse,
  WeatherResponse,
} from "../api/types";

const DEFAULT_POLL_INTERVAL_MS = 5000;
const HISTORY_LIMIT = 120;
const DEFAULT_PERFORMANCE_PERIOD: SummaryPeriod = "24h";

export interface StarlinkTelemetryState {
  status: TelemetrySample | null;
  history: StarlinkHistoryResponse | null;
  health: HealthResponse | null;
  starlinkHealth: StarlinkHealthResponse | null;
  dishInfo: DishInfoResponse | null;
  performance: StarlinkSummaryResponse | null;
  performancePeriod: SummaryPeriod;
  setPerformancePeriod: (period: SummaryPeriod) => void;
  weather: WeatherResponse | null;
  weatherImpact: WeatherImpactResponse | null;
  location: LocationResponse | null;
  outages: OutageSummaryResponse | null;
  isLoading: boolean;
  isUsingMockData: boolean;
  lastUpdated: Date | null;
}

export function useStarlinkTelemetry(pollIntervalMs: number = DEFAULT_POLL_INTERVAL_MS): StarlinkTelemetryState {
  const [performancePeriod, setPerformancePeriod] = useState<SummaryPeriod>(DEFAULT_PERFORMANCE_PERIOD);
  const [state, setState] = useState<Omit<StarlinkTelemetryState, "performancePeriod" | "setPerformancePeriod">>({
    status: null,
    history: null,
    health: null,
    starlinkHealth: null,
    dishInfo: null,
    performance: null,
    weather: null,
    weatherImpact: null,
    location: null,
    outages: null,
    isLoading: true,
    isUsingMockData: false,
    lastUpdated: null,
  });

  const isMountedRef = useRef(true);

  const refresh = useCallback(async () => {
    try {
      const [status, history, health, starlinkHealth, dishInfo, performance, weather, weatherImpact, location, outages] =
        await Promise.all([
          getStarlinkStatus(),
          getStarlinkHistory({ limit: HISTORY_LIMIT }),
          getHealth(),
          getStarlinkHealth(),
          getDishInfo(),
          getStarlinkSummary({ period: performancePeriod }),
          getWeather(),
          getWeatherImpact(),
          getLocation(),
          getOutages(),
        ]);

      if (!isMountedRef.current) return;
      setState({
        status,
        history,
        health,
        starlinkHealth,
        dishInfo,
        performance,
        weather,
        weatherImpact,
        location,
        outages,
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
        weather: generateMockWeather(),
        weatherImpact: generateMockWeatherImpact(),
        location: generateMockLocation(),
        outages: generateMockOutageSummary(),
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
