"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { type JudgeDimension, scoreColor, SCORE_COLORS, METRIC_LABELS } from "@/types/eval";

interface Props {
  dimensions: Record<string, JudgeDimension>;
}

function DimensionRow({ name, dim }: { name: string; dim: JudgeDimension }) {
  const [open, setOpen] = useState(false);
  const label  = METRIC_LABELS[name] ?? name;
  const color  = SCORE_COLORS[scoreColor(dim.score)];
  const pct    = Math.round(dim.score * 100);

  return (
    <div className="border border-slate-200 rounded-xl overflow-hidden hover:border-slate-300 transition-colors">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center gap-3 px-4 py-3.5 bg-white
                   hover:bg-slate-50/80 transition-colors text-left"
      >
        <span className="text-slate-400 shrink-0">
          {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        </span>

        <span className="flex-1 text-sm font-medium text-slate-700">{label}</span>

        {/* Score bar */}
        <div className="w-28 h-1.5 bg-slate-100 rounded-full overflow-hidden shrink-0">
          <div
            className="h-full rounded-full transition-all duration-500"
            style={{ width: `${pct}%`, backgroundColor: color }}
          />
        </div>

        <span
          className="w-10 text-right text-sm font-bold tabular-nums shrink-0"
          style={{ color }}
        >
          {pct}
        </span>
      </button>

      <AnimatePresence>
        {open && dim.explanation && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.18 }}
            className="overflow-hidden"
          >
            <div className="px-4 py-3.5 bg-slate-50 border-t border-slate-100
                            text-xs text-slate-600 leading-relaxed">
              {dim.explanation}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export default function JudgePanel({ dimensions }: Props) {
  const entries = Object.entries(dimensions).sort(([, a], [, b]) => b.score - a.score);

  if (!entries.length) {
    return (
      <p className="text-sm text-slate-400 italic">No judge dimensions evaluated.</p>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      {entries.map(([name, dim]) => (
        <DimensionRow key={name} name={name} dim={dim} />
      ))}
    </div>
  );
}
