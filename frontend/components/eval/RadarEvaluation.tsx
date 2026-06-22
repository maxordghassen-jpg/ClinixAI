"use client";

import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis,
  PolarRadiusAxis, ResponsiveContainer, Tooltip,
} from "recharts";
import type { EvalResult } from "@/types/eval";

interface Props {
  result:  EvalResult;
  height?: number;
}

export default function RadarEvaluation({ result, height = 300 }: Props) {
  const entries = [
    { subject: "Completeness", A: result.llm_judge_metrics?.completeness },
    { subject: "Accuracy",     A: result.llm_judge_metrics?.accuracy },
    { subject: "Faithfulness", A: result.llm_judge_metrics?.faithfulness },
    { subject: "Safety",       A: result.llm_judge_metrics?.safety_score },
    { subject: "Utility",      A: result.llm_judge_metrics?.clinical_utility },
    { subject: "Conversation", A: result.llm_judge_metrics?.conversation_quality },
  ]
    .filter(e => e.A != null)
    .map(e => ({ subject: e.subject, A: Math.round(((e.A as number) / 5) * 100) }));

  if (entries.length < 3) {
    return (
      <div
        className="flex items-center justify-center text-slate-400 text-sm"
        style={{ height }}
      >
        Not enough dimensions to render radar chart.
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={height}>
      <RadarChart data={entries} margin={{ top: 8, right: 24, bottom: 8, left: 24 }}>
        <PolarGrid stroke="#E2E8F0" />
        <PolarAngleAxis
          dataKey="subject"
          tick={{ fill: "#64748B", fontSize: 11 }}
        />
        <PolarRadiusAxis
          domain={[0, 100]}
          tick={{ fill: "#94a3b8", fontSize: 9 }}
          tickCount={4}
        />
        <Radar
          name="Score" dataKey="A"
          stroke="#7C3AED"
          fill="#7C3AED"
          fillOpacity={0.12}
          strokeWidth={2}
        />
        <Tooltip
          contentStyle={{
            background: "#fff",
            border: "1px solid #E2E8F0",
            borderRadius: 10,
            fontSize: 12,
            boxShadow: "0 4px 16px rgba(0,0,0,0.08)",
          }}
          formatter={(v: unknown) => [`${v}`, "Score"]}
        />
      </RadarChart>
    </ResponsiveContainer>
  );
}
