"use client";

import { useState } from "react";
import { Trash2 } from "lucide-react";
import { EvalSummary, scoreColor, SCORE_COLORS } from "@/types/eval";
import { deleteResult } from "@/lib/evalApi";

interface Props {
  rows: EvalSummary[];
  onSelect?: (id: string) => void;
  onDeleted?: (id: string) => void;
  compareIds?: [string, string] | [];
  onToggleCompare?: (id: string) => void;
}

function ScorePill({
  score,
  scale = "ratio",
}: {
  score?: number | null;
  scale?: "ratio" | "percent" | "five";
}) {
  if (score == null) return <span className="text-slate-400 text-xs">-</span>;
  const normalized = scale === "percent" ? score / 100 : scale === "five" ? score / 5 : score;
  const display = scale === "five" ? score.toFixed(1) : Math.round(scale === "percent" ? score : score * 100);
  const color = SCORE_COLORS[scoreColor(normalized)];
  return (
    <span
      className="inline-flex items-center justify-center min-w-10 h-6 rounded-md px-2 text-xs font-bold tabular-nums"
      style={{ color, background: `${color}18` }}
    >
      {display}
    </span>
  );
}

export default function EvaluationHistory({
  rows,
  onSelect,
  onDeleted,
  compareIds = [],
  onToggleCompare,
}: Props) {
  const [deleting, setDeleting] = useState<string | null>(null);

  async function handleDelete(id: string) {
    setDeleting(id);
    try {
      await deleteResult(id);
      onDeleted?.(id);
    } finally {
      setDeleting(null);
    }
  }

  if (!rows.length) {
    return (
      <div className="py-12 text-center bg-white rounded-lg border border-slate-200">
        <p className="text-sm text-slate-400">No evaluation history yet.</p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200 shadow-sm">
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr className="bg-slate-50 border-b border-slate-200">
            {onToggleCompare && <th className="px-3 py-3 w-8" />}
            <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase">Scenario</th>
            <th className="px-3 py-3 text-center text-xs font-semibold text-slate-500 uppercase">TSR</th>
            <th className="px-3 py-3 text-center text-xs font-semibold text-slate-500 uppercase">Completion</th>
            <th className="px-3 py-3 text-center text-xs font-semibold text-slate-500 uppercase">Faithfulness</th>
            <th className="px-3 py-3 text-center text-xs font-semibold text-slate-500 uppercase">Utility</th>
            <th className="px-3 py-3 text-center text-xs font-semibold text-slate-500 uppercase">Latency</th>
            <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase">Date</th>
            <th className="px-3 py-3 text-center text-xs font-semibold text-slate-500 uppercase">Lang</th>
            <th className="px-3 py-3 w-12" />
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {rows.map(row => {
            const isCompared = compareIds.includes(row.id as never);
            return (
              <tr
                key={row.id}
                className={`${isCompared ? "bg-blue-50" : "bg-white"} hover:bg-slate-50 cursor-pointer`}
                onClick={() => onSelect?.(row.id)}
              >
                {onToggleCompare && (
                  <td className="px-3 py-3" onClick={e => { e.stopPropagation(); onToggleCompare(row.id); }}>
                    <input type="checkbox" checked={isCompared} readOnly className="w-3.5 h-3.5 accent-blue-600" />
                  </td>
                )}
                <td className="px-4 py-3 text-slate-700 font-mono text-xs">
                  {row.scenario_id ?? <span className="text-slate-400 italic font-sans">manual</span>}
                </td>
                <td className="px-3 py-3 text-center">
                  <ScorePill score={row.task_success_rate} scale="percent" />
                </td>
                <td className="px-3 py-3 text-center">
                  <ScorePill score={row.workflow_completion_rate} scale="percent" />
                </td>
                <td className="px-3 py-3 text-center">
                  <ScorePill score={row.faithfulness} scale="five" />
                </td>
                <td className="px-3 py-3 text-center">
                  <ScorePill score={row.clinical_utility} scale="five" />
                </td>
                <td className="px-3 py-3 text-center text-slate-500 text-xs tabular-nums">
                  {row.latency_ms != null ? `${Math.round(row.latency_ms)}ms` : "-"}
                </td>
                <td className="px-4 py-3 text-slate-400 text-xs">
                  {new Date(row.evaluated_at).toLocaleString(undefined, {
                    month: "short",
                    day: "numeric",
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </td>
                <td className="px-3 py-3 text-center text-slate-400 text-xs font-mono uppercase">
                  {row.language.slice(0, 2)}
                </td>
                <td className="px-3 py-3" onClick={e => e.stopPropagation()}>
                  <button
                    onClick={() => handleDelete(row.id)}
                    disabled={deleting === row.id}
                    title="Delete"
                    className="text-slate-300 hover:text-rose-500 p-1 rounded hover:bg-rose-50"
                  >
                    {deleting === row.id ? <span className="text-xs">...</span> : <Trash2 size={13} />}
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
