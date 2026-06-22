"use client";

import { motion } from "framer-motion";
import { scoreColor, SCORE_COLORS, type ScoreColor } from "@/types/eval";

interface Props {
  label:        string;
  value?:       number | null;
  unit?:        string;
  description?: string;
  inverted?:    boolean;
  icon?:        React.ReactNode;
}

export default function MetricCard({ label, value, unit, description, inverted, icon }: Props) {
  const display  = value != null ? `${(value * 100).toFixed(1)}${unit ?? "%"}` : "—";
  const colorKey: ScoreColor = value == null
    ? "slate"
    : inverted ? scoreColor(1 - value) : scoreColor(value);
  const color    = SCORE_COLORS[colorKey];
  const barPct   = value != null ? Math.round(Math.max(0, Math.min(1, value)) * 100) : 0;

  return (
    <motion.div
      whileHover={{ y: -2 }}
      transition={{ duration: 0.15 }}
      className="bg-white border border-slate-200 rounded-2xl p-4 flex flex-col gap-3
                 shadow-sm hover:shadow-md transition-shadow cursor-default"
    >
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          {icon && <span className="text-slate-400 shrink-0">{icon}</span>}
          <span className="text-xs font-medium text-slate-500 uppercase tracking-wide truncate">
            {label}
          </span>
        </div>
        <span className="text-lg font-bold tabular-nums shrink-0" style={{ color }}>
          {display}
        </span>
      </div>

      {/* Progress bar */}
      <div className="w-full h-1.5 bg-slate-100 rounded-full overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-700 ease-out"
          style={{ width: `${barPct}%`, backgroundColor: color }}
        />
      </div>

      {description && (
        <p className="text-xs text-slate-400 leading-snug">{description}</p>
      )}
    </motion.div>
  );
}
