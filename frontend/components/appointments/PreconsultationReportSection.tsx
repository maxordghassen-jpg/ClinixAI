"use client";

import { Stethoscope, Sparkles } from "lucide-react";
import type { PreConsultationReport } from "@/types";

interface Props {
  report: PreConsultationReport | null;
  loading: boolean;
}

function Row({ label, value }: { label: string; value?: string | number | null }) {
  if (value == null || value === "") return null;
  return (
    <div className="flex justify-between items-baseline gap-2 py-1 border-b border-slate-50 last:border-0">
      <span className="text-xs text-slate-400 shrink-0">{label}</span>
      <span className="text-xs font-medium text-slate-700 text-right">{String(value)}</span>
    </div>
  );
}

function TagList({ items }: { items?: string[] }) {
  if (!items?.length) return null;
  return (
    <div className="flex flex-wrap gap-1">
      {items.map((item, i) => (
        <span
          key={i}
          className="text-[11px] px-2 py-0.5 bg-slate-100 text-slate-600 rounded-full"
        >
          {item}
        </span>
      ))}
    </div>
  );
}

export default function PreconsultationReportSection({ report, loading }: Props) {
  if (loading) {
    return (
      <div className="flex items-center gap-2 py-2">
        <div className="w-4 h-4 border-2 border-indigo-300 border-t-indigo-600 rounded-full animate-spin" />
        <p className="text-xs text-slate-400">Loading report…</p>
      </div>
    );
  }

  const pc = report?.preconsultation_snapshot;
  const hasClinical = !!(
    pc?.chief_complaint ||
    pc?.duration ||
    pc?.severity != null ||
    pc?.associated_symptoms?.length ||
    report?.ai_summary
  );

  if (!report || !hasClinical) {
    return <p className="text-xs text-slate-400 py-1">No preconsultation report available.</p>;
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-1.5">
        <Stethoscope size={12} className="text-indigo-400" />
        <h4 className="text-[10px] font-semibold text-slate-400 uppercase tracking-widest">
          Preconsultation Report
        </h4>
      </div>

      <Row label="Main Complaint" value={pc?.chief_complaint} />
      <Row label="Duration" value={pc?.duration} />
      <Row label="Severity" value={pc?.severity != null ? `${pc.severity}/10` : null} />

      {(pc?.associated_symptoms?.length ?? 0) > 0 && (
        <div>
          <p className="text-[10px] text-slate-400 mb-1">Associated Symptoms</p>
          <TagList items={pc?.associated_symptoms} />
        </div>
      )}

      {report.ai_summary && (
        <div>
          <p className="text-[10px] text-slate-400 mb-1 flex items-center gap-1">
            <Sparkles size={11} className="text-indigo-400" /> AI Summary
          </p>
          <div className="bg-indigo-50 border border-indigo-100 rounded-xl p-3">
            <p className="text-xs text-slate-700 leading-relaxed whitespace-pre-wrap">
              {report.ai_summary}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
