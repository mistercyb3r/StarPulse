import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { TelemetrySample } from "../../api/types";
import { formatClockTime } from "../../utils/format";
import { ChartCard } from "./ChartCard";
import { ChartTooltip } from "./ChartTooltip";

interface PowerHistoryChartProps {
  samples: TelemetrySample[];
}

interface PowerPoint {
  time: string;
  powerWatts: number | null;
}

function toPowerPoints(samples: TelemetrySample[]): PowerPoint[] {
  return samples.map((sample) => ({
    time: formatClockTime(sample.timestamp),
    powerWatts: sample.power_watts,
  }));
}

export function PowerHistoryChart({ samples }: PowerHistoryChartProps) {
  const data = toPowerPoints(samples);

  return (
    <ChartCard title="Power Usage History" subtitle="Dish power draw (watts)">
      <ResponsiveContainer width="100%" height={260}>
        <AreaChart data={data} margin={{ top: 8, right: 12, left: -12, bottom: 0 }}>
          <defs>
            <linearGradient id="powerGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="var(--accent-3)" stopOpacity={0.35} />
              <stop offset="95%" stopColor="var(--accent-3)" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" vertical={false} />
          <XAxis dataKey="time" tick={{ fill: "var(--text-muted)", fontSize: 11 }} minTickGap={40} />
          <YAxis tick={{ fill: "var(--text-muted)", fontSize: 11 }} width={44} />
          <Tooltip content={(props) => <ChartTooltip {...props} unit=" W" />} />
          <Area
            type="monotone"
            dataKey="powerWatts"
            name="Power"
            stroke="var(--accent-3)"
            fill="url(#powerGradient)"
            strokeWidth={2}
            isAnimationActive={false}
            connectNulls
          />
        </AreaChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}
