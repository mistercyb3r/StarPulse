import { Area, AreaChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { TelemetrySample } from "../../api/types";
import { formatClockTime } from "../../utils/format";
import { ChartCard } from "./ChartCard";
import { ChartTooltip } from "./ChartTooltip";

interface SpeedHistoryChartProps {
  samples: TelemetrySample[];
}

interface SpeedPoint {
  time: string;
  downloadMbps: number | null;
  uploadMbps: number | null;
}

function toMbps(bps: number | null): number | null {
  return bps === null ? null : Math.round((bps / 1_000_000) * 10) / 10;
}

function toSpeedPoints(samples: TelemetrySample[]): SpeedPoint[] {
  return samples.map((sample) => ({
    time: formatClockTime(sample.timestamp),
    downloadMbps: toMbps(sample.download_bps),
    uploadMbps: toMbps(sample.upload_bps),
  }));
}

export function SpeedHistoryChart({ samples }: SpeedHistoryChartProps) {
  const data = toSpeedPoints(samples);

  return (
    <ChartCard title="Speed History" subtitle="Download / upload throughput (Mbps)">
      <ResponsiveContainer width="100%" height={260}>
        <AreaChart data={data} margin={{ top: 8, right: 12, left: -12, bottom: 0 }}>
          <defs>
            <linearGradient id="downloadGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="var(--accent)" stopOpacity={0.35} />
              <stop offset="95%" stopColor="var(--accent)" stopOpacity={0} />
            </linearGradient>
            <linearGradient id="uploadGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="var(--accent-2)" stopOpacity={0.35} />
              <stop offset="95%" stopColor="var(--accent-2)" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" vertical={false} />
          <XAxis dataKey="time" tick={{ fill: "var(--text-muted)", fontSize: 11 }} minTickGap={40} />
          <YAxis tick={{ fill: "var(--text-muted)", fontSize: 11 }} width={44} />
          <Tooltip content={(props) => <ChartTooltip {...props} unit=" Mbps" />} />
          <Legend wrapperStyle={{ fontSize: 12, color: "var(--text-muted)" }} />
          <Area
            type="monotone"
            dataKey="downloadMbps"
            name="Download"
            stroke="var(--accent)"
            fill="url(#downloadGradient)"
            strokeWidth={2}
            isAnimationActive={false}
            connectNulls
          />
          <Area
            type="monotone"
            dataKey="uploadMbps"
            name="Upload"
            stroke="var(--accent-2)"
            fill="url(#uploadGradient)"
            strokeWidth={2}
            isAnimationActive={false}
            connectNulls
          />
        </AreaChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}
