"use client";

import { useEffect, useState } from "react";
import { ClipboardList, AlertTriangle, Clock, Thermometer, Loader2 } from "lucide-react";
import { getPreconsultationSummary } from "@/lib/api";
import type { PreconsultationSummary, PreconsultationUrgency } from "@/types";

const URGENCY_CONFIG: Record<
  PreconsultationUrgency,
  { label: string; cls: string; border: string }
> = {
  high:   { label: "High",   cls: "bg-rose-50 text-rose-700 border-rose-200",   border: "border-rose-200" },
  medium: { label: "Medium", cls: "bg-amber-50 text-amber-700 border-amber-200", border: "border-amber-200" },
  low:    { label: "Low",    cls: "bg-emerald-50 text-emerald-700 border-emerald-200", border: "border-emerald-200" },
};

function SeverityBar({ value }: { value: number }) {
  const pct = Math.round((value / 10) * 100);
  const color =
    value >= 8 ? "bg-rose-400" :
    value >= 5 ? "bg-amber-400" :
    "bg-emerald-400";
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-2 rounded-full bg-slate-100 overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs font-semibold text-slate-700 w-8 text-right">{value}/10</span>
    </div>
  );
}

interface Props {
  patientId: string;
}

export default function PreconsultationSummaryPanel({ patientId }: Props) {
  const [data, setData]       = useState<PreconsultationSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [missing, setMissing] = useState(false);
  const [error, setError]     = useState<string | null>(null);

  useEffect(() => {
    if (!patientId) return;
    setLoading(true);
    setMissing(false);
    setError(null);

    getPreconsultationSummary(patientId)
      .then(setData)
      .catch((e: Error) => {
        if (e.message.includes("404")) setMissing(true);
        else setError(e.message);
      })
      .finally(() => setLoading(false));
  }, [patientId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 size={18} className="animate-spin text-indigo-400" />
      </div>
    );
  }

  if (missing) {
    return (
      <div className="card p-4 text-center text-xs text-slate-400">
        No pre-consultation questionnaire completed yet.
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="card p-4 text-center text-xs text-rose-400">
        {error ?? "Failed to load pre-consultation data."}
      </div>
    );
  }

  const urgency = URGENCY_CONFIG[data.urgency] ?? URGENCY_CONFIG.low;
  const date = data.created_at
    ? new Date(data.created_at).toLocaleDateString(undefined, {
        year: "numeric", month: "short", day: "numeric",
      })
    : null;

  return (
    <div className="card p-4 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1.5">
          <ClipboardList size={11} /> Pre-Consultation
        </h4>
        {date && (
          <span className="flex items-center gap-1 text-xs text-slate-400">
            <Clock size={10} /> {date}
          </span>
        )}
      </div>

      {/* Urgency badge */}
      <span className={`inline-flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-full border ${urgency.cls}`}>
        <AlertTriangle size={11} />
        Urgency: {urgency.label}
      </span>

      {/* Chief complaint + duration */}
      <div className="space-y-1">
        <p className="text-xs font-medium text-slate-600">Chief Complaint</p>
        <p className="text-sm text-slate-800">{data.chief_complaint}</p>
        <p className="text-xs text-slate-400">Duration: {data.duration}</p>
      </div>

      {/* Severity */}
      <div className="space-y-1">
        <p className="text-xs font-medium text-slate-600 flex items-center gap-1">
          <Thermometer size={10} /> Severity
        </p>
        <SeverityBar value={data.severity} />
      </div>

      {/* Associated symptoms */}
      {data.associated_symptoms.length > 0 && (
        <div>
          <p className="text-xs font-medium text-slate-600 mb-1.5">Associated Symptoms</p>
          <div className="flex flex-wrap gap-1.5">
            {data.associated_symptoms.map((s) => (
              <span
                key={s}
                className="text-xs px-2.5 py-0.5 rounded-full bg-slate-50 text-slate-600 border border-slate-200"
              >
                {s}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Doctor narrative */}
      {data.summary_text && (
        <div className="border-t border-slate-50 pt-3">
          <p className="text-xs font-medium text-slate-500 mb-1">Clinical Summary</p>
          <p className="text-xs text-slate-600 leading-relaxed">{data.summary_text}</p>
        </div>
      )}
    </div>
  );
}
