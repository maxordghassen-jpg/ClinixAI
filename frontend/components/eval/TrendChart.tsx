"use client";

import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer,
} from "recharts";
import type { TrendPoint } from "@/types/eval";

interface Props {
  points:  TrendPoint[];
  height?: number;
}

function fmt(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      month: "short", day: "numeric",
    });
  } catch {
    return iso.slice(0, 10);
  }
}

export default function TrendChart({ points, height = 280 }: Props) {
  if (!points.length) {
    return (
      <div className="flex items-center justify-center text-slate-400 text-sm" style={{ height }}>
        No trend data yet — run some evaluations to see the evolution chart.
      </div>
    );
  }

  const data = points.map(p => ({
    name:    fmt(p.evaluated_at),
    overall: p.overall_score      != null ? +(p.overall_score      * 100).toFixed(1) : null,
    safety:  p.safety_score       != null ? +(p.safety_score       * 100).toFixed(1) : null,
    risk:    p.hallucination_risk != null  ? +(p.hallucination_risk * 100).toFixed(1) : null,
  }));

  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 8, right: 16, left: -8, bottom: 0 }}>
        <defs>
          <linearGradient id="trendGradOverall" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%"  stopColor="#7C3AED" stopOpacity={0.15} />
            <stop offset="95%" stopColor="#7C3AED" stopOpacity={0}    />
          </linearGradient>
          <linearGradient id="trendGradSafety" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%"  stopColor="#10B981" stopOpacity={0.12} />
            <stop offset="95%" stopColor="#10B981" stopOpacity={0}    />
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
          domain={[0, 100]}
          tick={{ fill: "#64748B", fontSize: 11 }}
          tickLine={false}
          axisLine={false}
          tickFormatter={v => `${v}`}
        />
        <Tooltip
          contentStyle={{
            background: "#fff",
            border: "1px solid #E2E8F0",
            borderRadius: 10,
            fontSize: 12,
            boxShadow: "0 4px 16px rgba(0,0,0,0.08)",
          }}
          labelStyle={{ color: "#0F172A", fontWeight: 600 }}
          formatter={(v: unknown) => [`${v}%`, ""]}
          cursor={{ stroke: "#E2E8F0", strokeWidth: 1 }}
        />
        <Legend
          wrapperStyle={{ fontSize: 12, color: "#64748B", paddingTop: 8 }}
          iconType="circle"
          iconSize={8}
        />

        <Area
          type="monotone" dataKey="overall" name="Overall"
          stroke="#7C3AED" strokeWidth={2}
          fill="url(#trendGradOverall)"
          dot={false} connectNulls
        />
        <Area
          type="monotone" dataKey="safety" name="Safety"
          stroke="#10B981" strokeWidth={2}
          fill="url(#trendGradSafety)"
          dot={false} connectNulls
        />
        <Area
          type="monotone" dataKey="risk" name="Halluc. Risk"
          stroke="#EF4444" strokeWidth={2}
          fill="none" strokeDasharray="4 2"
          dot={false} connectNulls
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
