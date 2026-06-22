"use client";

import {
  X,
  AlertTriangle,
  AlertCircle,
  CheckCircle,
  Stethoscope,
  User,
  Activity,
  Heart,
  FileText,
  Phone,
} from "lucide-react";
import type { PreConsultationReport } from "@/types";

interface Props {
  report: PreConsultationReport;
  appointmentDate?: string;
  appointmentTime?: string;
  onClose: () => void;
}

const URGENCY = {
  high:   { label: "High Urgency",   bg: "bg-red-50 border-red-200 text-red-700",     Icon: AlertTriangle },
  medium: { label: "Medium Urgency", bg: "bg-amber-50 border-amber-200 text-amber-700", Icon: AlertCircle   },
  low:    { label: "Low Urgency",    bg: "bg-emerald-50 border-emerald-200 text-emerald-700", Icon: CheckCircle },
} as const;

function Section({
  title,
  icon: Icon,
  children,
}: {
  title: string;
  icon: React.ElementType;
  children: React.ReactNode;
}) {
  return (
    <div className="mb-5">
      <div className="flex items-center gap-1.5 mb-2">
        <Icon size={12} className="text-indigo-400" />
        <h4 className="text-[10px] font-semibold text-slate-400 uppercase tracking-widest">
          {title}
        </h4>
      </div>
      {children}
    </div>
  );
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
  if (!items?.length)
    return <span className="text-xs text-slate-300 italic">None reported</span>;
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

export default function ReportPanel({
  report,
  appointmentDate,
  appointmentTime,
  onClose,
}: Props) {
  const p  = report.patient_snapshot;
  const pc = report.preconsultation_snapshot;
  const urgencyKey = (pc.urgency ?? "low") as keyof typeof URGENCY;
  const urg = URGENCY[urgencyKey] ?? URGENCY.low;
  const UrgIcon = urg.Icon;

  const hasProfile      = !!(p.name || p.weight || p.blood_type);
  const hasClinical     = !!(pc.chief_complaint || pc.associated_symptoms?.length);
  const hasNoData       = !hasProfile && !hasClinical && !report.ai_summary;
  const generatedDate   = new Date(report.created_at).toLocaleDateString("en-GB", {
    day: "2-digit", month: "short", year: "numeric",
  });

  return (
    <>
      {/* ── Header ──────────────────────────────────────────── */}
      <div className="flex items-center justify-between p-4 border-b border-slate-100 sticky top-0 bg-white z-10">
        <div>
          <p className="text-sm font-semibold text-slate-800">Pre-Consultation Report</p>
          <p className="text-xs text-slate-400">
            {appointmentDate
              ? `${appointmentDate}${appointmentTime ? ` · ${appointmentTime}` : ""}`
              : `Generated ${generatedDate}`}
          </p>
        </div>
        <button
          onClick={onClose}
          className="p-1.5 rounded-lg hover:bg-slate-100 transition-colors"
        >
          <X size={16} className="text-slate-500" />
        </button>
      </div>

      {/* ── Body ────────────────────────────────────────────── */}
      <div className="p-4 flex-1 overflow-y-auto">

        {hasNoData ? (
          <div className="flex flex-col items-center justify-center py-12 gap-3 text-center">
            <div className="w-12 h-12 rounded-2xl bg-slate-100 flex items-center justify-center">
              <FileText size={20} className="text-slate-300" />
            </div>
            <p className="text-sm text-slate-500 font-medium">No pre-consultation data</p>
            <p className="text-xs text-slate-400">
              The patient did not complete a symptom questionnaire before this appointment.
            </p>
          </div>
        ) : (
          <>
            {/* Urgency badge */}
            {pc.urgency && (
              <div className={`flex items-center gap-2 px-3 py-2.5 rounded-xl border mb-5 ${urg.bg}`}>
                <UrgIcon size={14} />
                <span className="text-xs font-semibold">{urg.label}</span>
                {typeof pc.severity === "number" && (
                  <span className="ml-auto text-xs opacity-70 font-medium">
                    Severity {pc.severity}/10
                  </span>
                )}
              </div>
            )}

            {/* Patient information */}
            <Section title="Patient Information" icon={User}>
              <Row label="Name"   value={p.name} />
              <Row label="Gender" value={p.gender} />
              <Row label="DOB"    value={p.date_of_birth} />
              <Row label="Phone"  value={p.phone} />
            </Section>

            {/* Vitals */}
            {(p.weight != null || p.height != null || p.blood_type) && (
              <Section title="Vitals" icon={Activity}>
                <Row label="Weight"     value={p.weight != null ? `${p.weight} kg` : null} />
                <Row label="Height"     value={p.height != null ? `${p.height} cm` : null} />
                <Row label="Blood Type" value={p.blood_type} />
              </Section>
            )}

            {/* Chief complaint */}
            {pc.chief_complaint && (
              <Section title="Chief Complaint" icon={Stethoscope}>
                <p className="text-sm font-semibold text-slate-800 mb-1.5">
                  {pc.chief_complaint}
                </p>
                <Row label="Duration" value={pc.duration} />
              </Section>
            )}

            {/* Associated symptoms */}
            {(pc.associated_symptoms?.length ?? 0) > 0 && (
              <Section title="Associated Symptoms" icon={AlertCircle}>
                <TagList items={pc.associated_symptoms} />
              </Section>
            )}

            {/* Lifestyle */}
            {(p.smoking_status || p.alcohol_consumption) && (
              <Section title="Lifestyle" icon={Heart}>
                <Row label="Smoking" value={p.smoking_status} />
                <Row label="Alcohol" value={p.alcohol_consumption} />
              </Section>
            )}

            {/* Medical History */}
            {(p.allergies?.length ||
              p.chronic_conditions?.length ||
              p.current_medications?.length ||
              p.past_surgeries?.length ||
              p.family_history?.length) ? (
              <Section title="Medical History" icon={FileText}>
                <div className="space-y-3">
                  <div>
                    <p className="text-[10px] text-slate-400 mb-1">Allergies</p>
                    <TagList items={p.allergies} />
                  </div>
                  <div>
                    <p className="text-[10px] text-slate-400 mb-1">Chronic Conditions</p>
                    <TagList items={p.chronic_conditions} />
                  </div>
                  <div>
                    <p className="text-[10px] text-slate-400 mb-1">Current Medications</p>
                    <TagList items={p.current_medications} />
                  </div>
                  {(p.past_surgeries?.length ?? 0) > 0 && (
                    <div>
                      <p className="text-[10px] text-slate-400 mb-1">Past Surgeries</p>
                      <TagList items={p.past_surgeries} />
                    </div>
                  )}
                  {(p.family_history?.length ?? 0) > 0 && (
                    <div>
                      <p className="text-[10px] text-slate-400 mb-1">Family History</p>
                      <TagList items={p.family_history} />
                    </div>
                  )}
                </div>
              </Section>
            ) : null}

            {/* Emergency Contact */}
            {p.emergency_contact_name && (
              <Section title="Emergency Contact" icon={Phone}>
                <Row label="Name"         value={p.emergency_contact_name} />
                <Row label="Phone"        value={p.emergency_contact_phone} />
                <Row label="Relationship" value={p.emergency_contact_relationship} />
              </Section>
            )}

            {/* AI Summary */}
            {report.ai_summary && (
              <Section title="AI Clinical Summary" icon={Stethoscope}>
                <div className="bg-indigo-50 border border-indigo-100 rounded-xl p-3">
                  <p className="text-xs text-slate-700 leading-relaxed whitespace-pre-wrap">
                    {report.ai_summary}
                  </p>
                </div>
                <p className="text-[10px] text-slate-400 mt-1.5 text-right">
                  Generated by ClinixAI · {generatedDate}
                </p>
              </Section>
            )}
          </>
        )}
      </div>
    </>
  );
}
