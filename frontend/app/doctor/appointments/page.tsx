"use client";

import { useEffect, useState, useCallback } from "react";
import { Search, Filter, X } from "lucide-react";
import TopBar from "@/components/layout/TopBar";
import AppointmentCard from "@/components/appointments/AppointmentCard";
import MedicalProfileSummary from "@/components/profile/MedicalProfileSummary";
import ReportPanel from "@/components/doctor/ReportPanel";
import { getDoctorWeekAppointments, confirmAppointment, cancelAppointment } from "@/services/api/appointments";
import { getAppointmentReport } from "@/lib/api";
import { useIdentity } from "@/hooks/useIdentity";
import { cn } from "@/lib/utils";
import type { Appointment, AppointmentStatus, PreConsultationReport } from "@/types";

const STATUS_TABS: { label: string; value: AppointmentStatus | "all" }[] = [
  { label: "All",       value: "all"       },
  { label: "Pending",   value: "pending"   },
  { label: "Confirmed", value: "confirmed" },
  { label: "Cancelled", value: "cancelled" },
];

export default function DoctorAppointmentsPage() {
  const { doctorId } = useIdentity();
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [loading, setLoading]           = useState(true);
  const [filter, setFilter]             = useState<AppointmentStatus | "all">("all");
  const [search, setSearch]             = useState("");

  const [selectedApt, setSelectedApt]     = useState<Appointment | null>(null);
  const [reportApt, setReportApt]         = useState<Appointment | null>(null);
  const [reportData, setReportData]       = useState<PreConsultationReport | null>(null);
  const [reportLoading, setReportLoading] = useState(false);

  const fetchAppointments = useCallback(async () => {
    if (!doctorId) return;
    setLoading(true);
    try {
      const apts = await getDoctorWeekAppointments(doctorId).catch(() => []);
      setAppointments(apts);
    } finally {
      setLoading(false);
    }
  }, [doctorId]);

  useEffect(() => { fetchAppointments(); }, [fetchAppointments]);

  async function handleConfirm(id: string) {
    await confirmAppointment(id).catch(console.error);
    fetchAppointments();
  }

  async function handleCancel(id: string) {
    await cancelAppointment(id).catch(console.error);
    fetchAppointments();
  }

  async function handleViewReport(apt: Appointment) {
    setReportApt(apt);
    setReportData(null);
    setReportLoading(true);
    try {
      const report = await getAppointmentReport(apt.id);
      setReportData(report);
    } catch {
      setReportData(null);
    } finally {
      setReportLoading(false);
    }
  }

  const filtered = appointments.filter((a) => {
    if (filter !== "all" && a.status !== filter) return false;
    if (search) {
      const q = search.toLowerCase();
      return (
        a.patient_name?.toLowerCase().includes(q) ||
        a.specialty?.toLowerCase().includes(q) ||
        a.date.includes(q)
      );
    }
    return true;
  });

  return (
    <div className="flex flex-col min-h-full">
      <TopBar title="Appointments" subtitle="Manage your patient appointments" />

      {/* Pre-consultation report side panel */}
      {reportApt && (
        <div className="fixed inset-0 z-50 flex">
          <div
            className="flex-1 bg-black/30 backdrop-blur-sm"
            onClick={() => { setReportApt(null); setReportData(null); }}
          />
          <div className="w-full max-w-sm bg-white shadow-2xl overflow-y-auto flex flex-col">
            {reportLoading ? (
              <div className="flex flex-col items-center justify-center h-64 gap-3">
                <div className="w-6 h-6 border-2 border-indigo-300 border-t-indigo-600 rounded-full animate-spin" />
                <p className="text-xs text-slate-400">Loading report…</p>
              </div>
            ) : reportData ? (
              <ReportPanel
                report={reportData}
                appointmentDate={reportApt.date}
                appointmentTime={reportApt.time}
                onClose={() => { setReportApt(null); setReportData(null); }}
              />
            ) : (
              <div className="flex flex-col items-center justify-center h-64 gap-3 p-6 text-center">
                <p className="text-sm font-medium text-slate-600">No report available</p>
                <p className="text-xs text-slate-400">
                  A report is generated automatically when the patient books via the AI assistant.
                </p>
                <button
                  onClick={() => { setReportApt(null); setReportData(null); }}
                  className="text-xs text-indigo-600 hover:underline mt-2"
                >
                  Close
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Patient medical profile side panel */}
      {selectedApt && (
        <div className="fixed inset-0 z-40 flex">
          <div
            className="flex-1 bg-black/30 backdrop-blur-sm"
            onClick={() => setSelectedApt(null)}
          />
          <div className="w-full max-w-sm bg-white shadow-2xl overflow-y-auto flex flex-col">
            <div className="flex items-center justify-between p-4 border-b border-slate-100 sticky top-0 bg-white z-10">
              <div>
                <p className="text-sm font-semibold text-slate-800">Patient Profile</p>
                <p className="text-xs text-slate-400">
                  {selectedApt.date} · {selectedApt.time}
                </p>
              </div>
              <button
                onClick={() => setSelectedApt(null)}
                className="p-1.5 rounded-lg hover:bg-slate-100 transition-colors"
              >
                <X size={16} className="text-slate-500" />
              </button>
            </div>
            <div className="p-4 flex-1">
              <MedicalProfileSummary
                patientId={selectedApt.patient_id}
                patientName={selectedApt.patient_name}
              />
            </div>
          </div>
        </div>
      )}

      <div className="flex-1 p-6 space-y-5">
        {/* Filters */}
        <div className="flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1 max-w-sm">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search patient, specialty…"
              className="w-full pl-9 pr-4 py-2 text-sm bg-white border border-slate-200 rounded-xl focus:outline-none focus:border-indigo-300 focus:ring-2 focus:ring-indigo-100"
            />
          </div>
          <div className="flex items-center gap-1 bg-white border border-slate-200 rounded-xl p-1">
            <Filter size={13} className="text-slate-400 ml-2" />
            {STATUS_TABS.map((tab) => (
              <button
                key={tab.value}
                onClick={() => setFilter(tab.value)}
                className={cn(
                  "px-3 py-1 text-xs font-medium rounded-lg transition-colors",
                  filter === tab.value
                    ? "bg-indigo-600 text-white shadow-sm"
                    : "text-slate-600 hover:bg-slate-100"
                )}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        {/* Count */}
        <p className="text-xs text-slate-500">
          {filtered.length} appointment{filtered.length !== 1 ? "s" : ""}
        </p>

        {/* List */}
        {loading ? (
          <div className="space-y-3">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="card p-4 animate-pulse">
                <div className="flex gap-3">
                  <div className="w-12 h-12 rounded-xl bg-slate-100" />
                  <div className="flex-1 space-y-2">
                    <div className="h-3 bg-slate-100 rounded w-1/3" />
                    <div className="h-2.5 bg-slate-100 rounded w-1/2" />
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <div className="card p-10 flex flex-col items-center justify-center text-center gap-3">
            <p className="text-sm font-medium text-slate-600">No appointments found</p>
            <p className="text-xs text-slate-400">Try adjusting your filters</p>
          </div>
        ) : (
          <div className="space-y-3">
            {filtered.map((apt) => (
              <div key={apt.id} onClick={() => setSelectedApt(apt)} className="cursor-pointer">
                <AppointmentCard
                  appointment={apt}
                  role="doctor"
                  onConfirm={handleConfirm}
                  onCancel={handleCancel}
                  onViewReport={() => handleViewReport(apt)}
                />
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
