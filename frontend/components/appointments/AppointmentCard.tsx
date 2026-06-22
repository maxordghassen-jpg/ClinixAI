"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { CalendarDays, Clock, User, Check, X, ArrowRight, FileText, ChevronDown, ChevronRight } from "lucide-react";
import StatusBadge from "./StatusBadge";
import PreconsultationReportSection from "./PreconsultationReportSection";
import { formatDate, formatTime, getRelativeDay } from "@/lib/utils";
import { getAppointmentReport } from "@/lib/api";
import type { Appointment, PreConsultationReport } from "@/types";

interface Props {
  appointment: Appointment;
  role?: "patient" | "doctor";
  onConfirm?: (id: string) => void;
  onCancel?: (id: string) => void;
  onViewReport?: (id: string) => void;
  compact?: boolean;
}

export default function AppointmentCard({
  appointment: apt,
  role = "patient",
  onConfirm,
  onCancel,
  onViewReport,
  compact = false,
}: Props) {
  const relativeDay = getRelativeDay(apt.date);
  const counterpart = role === "patient" ? apt.doctor_name : apt.patient_name;

  const [expanded, setExpanded] = useState(false);
  const [report, setReport] = useState<PreConsultationReport | null>(null);
  const [reportLoading, setReportLoading] = useState(false);
  const [reportFetched, setReportFetched] = useState(false);

  async function handleToggle() {
    if (role !== "patient") return;
    setExpanded((prev) => !prev);
    if (!reportFetched) {
      setReportLoading(true);
      try {
        const data = await getAppointmentReport(apt.id);
        setReport(data);
      } catch {
        setReport(null);
      } finally {
        setReportLoading(false);
        setReportFetched(true);
      }
    }
  }

  return (
    <motion.div
      whileHover={{ y: -1 }}
      transition={{ duration: 0.15 }}
      onClick={handleToggle}
      className={`card p-4 flex gap-4 ${role === "patient" ? "cursor-pointer" : ""}`}
    >
      {/* Date block */}
      <div className="shrink-0 w-12 flex flex-col items-center justify-center bg-indigo-50 rounded-xl py-2 px-1 border border-indigo-100">
        <span className="text-[10px] font-semibold text-indigo-500 uppercase tracking-wider">
          {new Date(apt.date).toLocaleDateString("en-US", { month: "short" })}
        </span>
        <span className="text-xl font-bold text-indigo-700 leading-none mt-0.5">
          {new Date(apt.date).getDate()}
        </span>
      </div>

      {/* Info */}
      <div className="flex-1 min-w-0">
        <div className="flex items-start justify-between gap-2 mb-1.5">
          <div className="flex-1 min-w-0">
            {counterpart && (
              <p className="font-semibold text-slate-800 text-sm truncate">{counterpart}</p>
            )}
            {apt.specialty && (
              <p className="text-xs text-slate-500 truncate">{apt.specialty}</p>
            )}
          </div>
          <div className="flex items-center gap-1.5 shrink-0">
            <StatusBadge status={apt.status} />
            {role === "patient" && (
              <span className="text-slate-300">
                {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
              </span>
            )}
          </div>
        </div>

        <div className="flex items-center gap-3 text-xs text-slate-500">
          <span className="flex items-center gap-1">
            <CalendarDays size={11} />
            {relativeDay !== "Today" && relativeDay !== "Tomorrow"
              ? formatDate(apt.date)
              : relativeDay}
          </span>
          <span className="flex items-center gap-1">
            <Clock size={11} />
            {formatTime(apt.time)}
            {apt.end_time && ` — ${formatTime(apt.end_time)}`}
          </span>
        </div>

        {role === "patient" && (
          <AnimatePresence>
            {expanded && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: "auto", opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                transition={{ duration: 0.18 }}
                className="overflow-hidden"
              >
                <div
                  className="mt-3 pt-3 border-t border-slate-100"
                  onClick={(e) => e.stopPropagation()}
                >
                  <PreconsultationReportSection report={report} loading={reportLoading} />
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        )}

        {!compact && role === "doctor" && (
          <div className="flex items-center gap-2 mt-2.5">
            {apt.status === "pending" && onConfirm && (
              <button
                onClick={(e) => { e.stopPropagation(); onConfirm(apt.id); }}
                className="flex items-center gap-1 text-[11px] font-medium px-2.5 py-1 rounded-lg bg-emerald-50 text-emerald-700 hover:bg-emerald-100 border border-emerald-200 transition-colors"
              >
                <Check size={10} /> Confirm
              </button>
            )}
            {apt.status === "pending" && onCancel && (
              <button
                onClick={(e) => { e.stopPropagation(); onCancel(apt.id); }}
                className="flex items-center gap-1 text-[11px] font-medium px-2.5 py-1 rounded-lg bg-red-50 text-red-600 hover:bg-red-100 border border-red-200 transition-colors"
              >
                <X size={10} /> Cancel
              </button>
            )}
            {onViewReport && (
              <button
                onClick={(e) => { e.stopPropagation(); onViewReport(apt.id); }}
                className="flex items-center gap-1 text-[11px] font-medium px-2.5 py-1 rounded-lg bg-indigo-50 text-indigo-600 hover:bg-indigo-100 border border-indigo-200 transition-colors ml-auto"
              >
                <FileText size={10} /> View Report
              </button>
            )}
          </div>
        )}
      </div>
    </motion.div>
  );
}

/* ─── Compact list item variant ─────────────────────────── */
export function AppointmentRow({ appointment: apt, role = "patient" }: Omit<Props, "compact" | "onConfirm" | "onCancel">) {
  const counterpart = role === "patient" ? apt.doctor_name : apt.patient_name;
  return (
    <div className="flex items-center gap-3 py-3 border-b border-slate-100 last:border-0 group hover:bg-slate-50/60 -mx-4 px-4 transition-colors cursor-pointer">
      <div className="w-9 h-9 rounded-xl bg-indigo-50 flex items-center justify-center shrink-0 border border-indigo-100">
        <User size={14} className="text-indigo-500" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-slate-800 truncate">{counterpart ?? "—"}</p>
        <p className="text-xs text-slate-400 truncate">
          {getRelativeDay(apt.date)} · {formatTime(apt.time)}
        </p>
      </div>
      <StatusBadge status={apt.status} />
      <ArrowRight size={13} className="text-slate-300 group-hover:text-slate-400 transition-colors shrink-0" />
    </div>
  );
}
