"use client";

import { scoreColor, SCORE_COLORS } from "@/types/eval";

interface Props {
  score?:    number | null;
  size?:     number;
  stroke?:   number;
  label?:    string;
  sublabel?: string;
  animate?:  boolean;
}

export default function ScoreRing({
  score,
  size    = 120,
  stroke  = 10,
  label,
  sublabel,
  animate = true,
}: Props) {
  const r       = (size - stroke) / 2;
  const circ    = 2 * Math.PI * r;
  const pct     = score != null ? Math.max(0, Math.min(1, score)) : 0;
  const dash    = pct * circ;
  const color   = SCORE_COLORS[scoreColor(score)];
  const display = score != null ? `${Math.round(score * 100)}` : "—";

  return (
    <div className="flex flex-col items-center gap-1.5 select-none">
      <div style={{ width: size, height: size }} className="relative">
        <svg width={size} height={size} className="-rotate-90">
          {/* Track */}
          <circle
            cx={size / 2} cy={size / 2} r={r}
            fill="none"
            stroke="#E2E8F0"
            strokeWidth={stroke}
          />
          {/* Progress */}
          <circle
            cx={size / 2} cy={size / 2} r={r}
            fill="none"
            stroke={color}
            strokeWidth={stroke}
            strokeLinecap="round"
            strokeDasharray={`${dash} ${circ}`}
            style={animate ? { transition: "stroke-dasharray 0.8s cubic-bezier(.4,0,.2,1)" } : {}}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="font-bold leading-none" style={{ fontSize: size * 0.22, color }}>
            {display}
          </span>
          {score != null && (
            <span className="leading-none text-slate-400" style={{ fontSize: size * 0.11 }}>
              / 100
            </span>
          )}
        </div>
      </div>
      {label    && <span className="text-sm font-semibold text-slate-700">{label}</span>}
      {sublabel && <span className="text-xs text-slate-400">{sublabel}</span>}
    </div>
  );
}
