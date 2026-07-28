import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { TelemetrySample } from "../../api/types";
import { formatClockTime } from "../../utils/format";
import { ChartCard } from "./ChartCard";
import { ChartTooltip } from "./ChartTooltip";

interface LatencyHistoryChartProps {
  samples: TelemetrySample[];
}

interface LatencyPoint {
  time: string;
  latencyMs: number | null;
}

function toLatencyPoints(samples: TelemetrySample[]): LatencyPoint[] {
  return samples.map((sample) => ({
    time: formatClockTime(sample.timestamp),
    latencyMs: sample.latency_ms,
  }));
}

export function LatencyHistoryChart({ samples }: LatencyHistoryChartProps) {
  const data = toLatencyPoints(samples);

  return (
    <ChartCard title="Latency History" subtitle="Round-trip ping latency (ms)">
      <ResponsiveContainer width="100%" height={260}>
        <LineChart data={data} margin={{ top: 8, right: 12, left: -12, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" vertical={false} />
          <XAxis dataKey="time" tick={{ fill: "var(--text-muted)", fontSize: 11 }} minTickGap={40} />
          <YAxis tick={{ fill: "var(--text-muted)", fontSize: 11 }} width={44} />
          <Tooltip content={(props) => <ChartTooltip {...props} unit=" ms" />} />
          <Line
            type="monotone"
            dataKey="latencyMs"
            name="Latency"
            stroke="var(--accent-3)"
            strokeWidth={2}
            dot={false}
            isAnimationActive={false}
            connectNulls
          />
        </LineChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}
