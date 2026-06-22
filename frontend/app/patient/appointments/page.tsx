"use client";

import { useEffect, useState, useCallback } from "react";
import { Search, Filter, CalendarDays } from "lucide-react";
import TopBar from "@/components/layout/TopBar";
import AppointmentCard from "@/components/appointments/AppointmentCard";
import { useIdentity } from "@/hooks/useIdentity";
import { getPatientWeekAppointments, cancelAppointment } from "@/services/api/appointments";
import { cn } from "@/lib/utils";
import type { Appointment, AppointmentStatus } from "@/types";

const STATUS_TABS: { label: string; value: AppointmentStatus | "all" }[] = [
  { label: "All",       value: "all"       },
  { label: "Confirmed", value: "confirmed" },
  { label: "Pending",   value: "pending"   },
  { label: "Cancelled", value: "cancelled" },
];

export default function PatientAppointmentsPage() {
  const { patientId } = useIdentity();
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [loading, setLoading]           = useState(true);
  const [filter, setFilter]             = useState<AppointmentStatus | "all">("all");
  const [search, setSearch]             = useState("");

  const fetchAppointments = useCallback(async () => {
    if (!patientId) return;
    setLoading(true);
    try {
      const apts = await getPatientWeekAppointments(patientId).catch(() => []);
      setAppointments(apts);
    } finally {
      setLoading(false);
    }
  }, [patientId]);

  useEffect(() => { fetchAppointments(); }, [fetchAppointments]);

  async function handleCancel(id: string) {
    await cancelAppointment(id).catch(console.error);
    fetchAppointments();
  }

  const filtered = appointments.filter((a) => {
    if (filter !== "all" && a.status !== filter) return false;
    if (search) {
      const q = search.toLowerCase();
      return (
        a.doctor_name?.toLowerCase().includes(q) ||
        a.specialty?.toLowerCase().includes(q) ||
        a.date.includes(q)
      );
    }
    return true;
  });

  return (
    <div className="flex flex-col min-h-full">
      <TopBar title="My Appointments" subtitle="View and manage your upcoming visits" />

      <div className="flex-1 p-6 space-y-5">
        <div className="flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1 max-w-sm">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search doctor, specialty…"
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
                  filter === tab.value ? "bg-indigo-600 text-white shadow-sm" : "text-slate-600 hover:bg-slate-100"
                )}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        <p className="text-xs text-slate-500">
          {filtered.length} appointment{filtered.length !== 1 ? "s" : ""}
        </p>

        {loading ? (
          <div className="space-y-3">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="card p-4 animate-pulse">
                <div className="flex gap-3">
                  <div className="w-12 h-12 rounded-xl bg-slate-100" />
                  <div className="flex-1 space-y-2 py-1">
                    <div className="h-3 bg-slate-100 rounded w-1/3" />
                    <div className="h-2.5 bg-slate-100 rounded w-1/2" />
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <div className="card p-12 flex flex-col items-center justify-center text-center gap-4">
            <div className="w-14 h-14 rounded-2xl bg-indigo-50 flex items-center justify-center">
              <CalendarDays size={24} className="text-indigo-400" />
            </div>
            <div>
              <p className="text-sm font-semibold text-slate-700">No appointments found</p>
              <p className="text-xs text-slate-400 mt-1">
                {filter === "all" ? "Book your first appointment using the AI assistant" : "Try a different filter"}
              </p>
            </div>
            {filter === "all" && (
              <a href="/patient/doctors" className="btn-primary text-sm px-5 py-2">Find a Doctor</a>
            )}
          </div>
        ) : (
          <div className="space-y-3">
            {filtered.map((apt) => (
              <AppointmentCard key={apt.id} appointment={apt} role="patient" onCancel={handleCancel} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
