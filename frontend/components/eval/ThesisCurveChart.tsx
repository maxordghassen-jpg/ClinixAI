"use client";

import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer, ReferenceLine,
} from "recharts";
import { motion } from "framer-motion";

interface DataPoint {
  label: string;
  value: number | null;
}

interface Props {
  title:     string;
  subtitle?: string;
  data:      DataPoint[];
  color?:    string;
  height?:   number;
}

const ORANGE = "#F97316";
const RED    = "#EF4444";

export default function ThesisCurveChart({
  title, subtitle, data, color = ORANGE, height = 240,
}: Props) {
  const valid = data.filter(d => d.value != null && (d.value as number) > 0);
  const avg   = valid.length
    ? valid.reduce((s, d) => s + (d.value as number), 0) / valid.length
    : 0;
  const max   = valid.length ? Math.max(...valid.map(d => d.value as number)) : 0;
  const min   = valid.length ? Math.min(...valid.map(d => d.value as number)) : 0;

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="bg-white rounded-2xl border border-slate-200 shadow-sm p-5
                 hover:shadow-md transition-shadow"
    >
      {/* Header */}
      <div className="mb-4">
        <p className="text-sm font-semibold text-slate-800">{title}</p>
        {subtitle && (
          <p className="text-xs text-slate-400 mt-0.5">{subtitle}</p>
        )}
        {valid.length > 0 && (
          <div className="flex flex-wrap items-center gap-4 mt-2.5">
            <span className="text-xs text-slate-500">
              Avg:{" "}
              <span className="font-semibold tabular-nums" style={{ color: RED }}>
                {(avg * 100).toFixed(1)}%
              </span>
            </span>
            <span className="text-xs text-slate-500">
              Max:{" "}
              <span className="font-semibold tabular-nums" style={{ color }}>
                {(max * 100).toFixed(1)}%
              </span>
            </span>
            <span className="text-xs text-slate-500">
              Min:{" "}
              <span className="font-semibold tabular-nums text-slate-600">
                {(min * 100).toFixed(1)}%
              </span>
            </span>
            <span className="text-xs text-slate-400">
              n={valid.length}
            </span>
          </div>
        )}
      </div>

      {/* Empty state */}
      {valid.length === 0 ? (
        <div
          className="flex flex-col items-center justify-center gap-3 text-center"
          style={{ height }}
        >
          <div className="w-10 h-10 rounded-2xl bg-slate-100 flex items-center justify-center">
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
              <path
                d="M2 13.5L6 8l3 4 4-6 3 3"
                stroke="#CBD5E1"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </div>
          <p className="text-xs text-slate-400 max-w-[160px] leading-relaxed">
            Run evaluations to populate this chart.
          </p>
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={height}>
          <LineChart data={data} margin={{ top: 8, right: 28, left: -6, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" />
            <XAxis
              dataKey="label"
              tick={{ fill: "#64748B", fontSize: 10 }}
              tickLine={false}
              axisLine={{ stroke: "#E2E8F0" }}
              interval="preserveStartEnd"
            />
            <YAxis
              domain={[0, 1]}
              tick={{ fill: "#64748B", fontSize: 10 }}
              tickLine={false}
              axisLine={{ stroke: "#E2E8F0" }}
              tickFormatter={v => `${Math.round(v * 100)}%`}
            />
            <Tooltip
              contentStyle={{
                background: "#fff",
                border: "1px solid #E2E8F0",
                borderRadius: 10,
                fontSize: 12,
                boxShadow: "0 4px 16px rgba(0,0,0,0.08)",
              }}
              formatter={(v: unknown) => [`${((v as number) * 100).toFixed(2)}%`, title]}
              labelStyle={{ color: "#0F172A", fontWeight: 600, marginBottom: 2 }}
              cursor={{ stroke: "#E2E8F0", strokeWidth: 1 }}
            />
            {/* Average reference line */}
            <ReferenceLine
              y={avg}
              stroke={RED}
              strokeDasharray="5 3"
              strokeWidth={1.5}
              label={{
                value: `avg ${(avg * 100).toFixed(1)}%`,
                position: "insideTopRight",
                fill: RED,
                fontSize: 9,
                fontWeight: 600,
              }}
            />
            <Line
              type="monotone"
              dataKey="value"
              name={`${title} (avg ${(avg * 100).toFixed(1)}%)`}
              stroke={color}
              strokeWidth={2}
              dot={{ r: 4, fill: color, stroke: "#fff", strokeWidth: 2 }}
              activeDot={{ r: 6, fill: color, stroke: "#fff", strokeWidth: 2 }}
              connectNulls
            />
            <Legend
              wrapperStyle={{ fontSize: 11, paddingTop: 8, color: "#64748B" }}
              iconType="circle"
              iconSize={8}
            />
          </LineChart>
        </ResponsiveContainer>
      )}
    </motion.div>
  );
}
