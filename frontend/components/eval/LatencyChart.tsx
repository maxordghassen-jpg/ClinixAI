"use client";

import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine,
} from "recharts";
import type { TrendPoint } from "@/types/eval";

interface Props {
  points:  TrendPoint[];
  height?: number;
}

function fmt(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" });
  } catch {
    return iso.slice(0, 10);
  }
}

export default function LatencyChart({ points, height = 220 }: Props) {
  const data = points
    .filter(p => p.latency_ms != null)
    .map(p => ({ name: fmt(p.evaluated_at), latency: Math.round(p.latency_ms!) }));

  if (!data.length) {
    return (
      <div className="flex items-center justify-center text-slate-400 text-sm" style={{ height: Math.max(height * 0.5, 80) }}>
        No latency data yet.
      </div>
    );
  }

  const avg = Math.round(data.reduce((s, d) => s + d.latency, 0) / data.length);

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-semibold text-slate-600 uppercase tracking-wide">
          Evaluation Latency
        </span>
        <span className="text-xs text-slate-500">
          avg{" "}
          <span className="font-semibold text-violet-600 tabular-nums">{avg} ms</span>
        </span>
      </div>
      <ResponsiveContainer width="100%" height={height}>
        <AreaChart data={data} margin={{ top: 4, right: 12, left: -8, bottom: 0 }}>
          <defs>
            <linearGradient id="latGradLight" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%"  stopColor="#7C3AED" stopOpacity={0.15} />
              <stop offset="95%" stopColor="#7C3AED" stopOpacity={0}    />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" />
          <XAxis
            dataKey="name"
            tick={{ fill: "#64748B", fontSize: 11 }}
            tickLine={false}
            axisLine={false}
          />
          <YAxis
            tick={{ fill: "#64748B", fontSize: 11 }}
            tickLine={false}
            axisLine={false}
          />
          <Tooltip
            contentStyle={{
              background: "#fff",
              border: "1px solid #E2E8F0",
              borderRadius: 10,
              fontSize: 12,
              boxShadow: "0 4px 16px rgba(0,0,0,0.08)",
            }}
            formatter={(v: unknown) => [`${v} ms`, "Latency"]}
          />
          <ReferenceLine
            y={avg}
            stroke="#7C3AED"
            strokeDasharray="4 2"
            strokeOpacity={0.5}
            strokeWidth={1.5}
          />
          <Area
            type="monotone" dataKey="latency"
            stroke="#7C3AED" strokeWidth={2}
            fill="url(#latGradLight)"
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
