"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { Search, User, CalendarDays, X } from "lucide-react";
import TopBar from "@/components/layout/TopBar";
import MedicalProfileSummary from "@/components/profile/MedicalProfileSummary";
import { getDoctorWeekAppointments } from "@/services/api/appointments";
import { getPatientProfileForDoctor } from "@/lib/api";
import { useIdentity } from "@/hooks/useIdentity";
import { formatDate, formatTime, calcAge } from "@/lib/utils";
import StatusBadge from "@/components/appointments/StatusBadge";
import type { Appointment, PatientProfileOut } from "@/types";

export default function DoctorPatientsPage() {
  const { doctorId } = useIdentity();
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [loading, setLoading]           = useState(true);
  const [search, setSearch]             = useState("");
  const [profiles, setProfiles] = useState<Record<string, PatientProfileOut | null>>({});
  const [selected, setSelected] = useState<{ id: string; name: string } | null>(null);
  const fetchedProfiles = useRef<Set<string>>(new Set());

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

  // Load each patient's profile so the card can show their real name, age,
  // and phone instead of the raw patient_id.
  useEffect(() => {
    const ids = new Set(appointments.map((a) => a.patient_id));
    for (const id of ids) {
      if (fetchedProfiles.current.has(id)) continue;
      fetchedProfiles.current.add(id);
      getPatientProfileForDoctor(id)
        .then((profile) => setProfiles((prev) => ({ ...prev, [id]: profile })))
        .catch(() => setProfiles((prev) => ({ ...prev, [id]: null })));
    }
  }, [appointments]);

  const filtered = appointments.filter((a) => {
    if (!search) return true;
    const q = search.toLowerCase();
    const name = profiles[a.patient_id]?.name ?? a.patient_name;
    return name?.toLowerCase().includes(q) || a.specialty?.toLowerCase().includes(q);
  });

  const uniquePatients = Array.from(
    new Map(filtered.map((a) => [a.patient_id, a])).values()
  );

  return (
    <div className="flex flex-col min-h-full">
      <TopBar title="Patients" subtitle="Patients scheduled this week" />

      {/* Patient detail drawer */}
      {selected && (
        <div className="fixed inset-0 z-40 flex">
          <div
            className="flex-1 bg-black/30 backdrop-blur-sm"
            onClick={() => setSelected(null)}
          />
          <div className="w-full max-w-sm bg-white shadow-2xl overflow-y-auto flex flex-col">
            <div className="flex items-center justify-between p-4 border-b border-slate-100 sticky top-0 bg-white z-10">
              <p className="text-sm font-semibold text-slate-800">{selected.name}</p>
              <button
                onClick={() => setSelected(null)}
                className="p-1.5 rounded-lg hover:bg-slate-100 transition-colors"
              >
                <X size={16} className="text-slate-500" />
              </button>
            </div>
            <div className="p-4 flex-1 space-y-4">
              <MedicalProfileSummary patientId={selected.id} patientName={selected.name} />

              <div className="card p-4 space-y-1">
                <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                  <CalendarDays size={11} />
                  Appointments
                </h4>
                <div className="space-y-1.5">
                  {appointments
                    .filter((a) => a.patient_id === selected.id)
                    .map((a) => (
                      <div key={a.id} className="flex items-center gap-2 text-xs text-slate-500 py-1">
                        <CalendarDays size={11} className="shrink-0" />
                        <span>{formatDate(a.date)} · {formatTime(a.time)}</span>
                        <StatusBadge status={a.status} />
                      </div>
                    ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      <div className="flex-1 p-6 space-y-5">
        <div className="relative max-w-sm">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search patient name…"
            className="w-full pl-9 pr-4 py-2 text-sm bg-white border border-slate-200 rounded-xl focus:outline-none focus:border-indigo-300 focus:ring-2 focus:ring-indigo-100"
          />
        </div>

        <p className="text-xs text-slate-500">
          {uniquePatients.length} patient{uniquePatients.length !== 1 ? "s" : ""} this week
        </p>

        {loading ? (
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="card p-4 animate-pulse flex gap-3">
                <div className="w-10 h-10 rounded-xl bg-slate-100 shrink-0" />
                <div className="flex-1 space-y-2 py-1">
                  <div className="h-3 bg-slate-100 rounded w-1/4" />
                  <div className="h-2.5 bg-slate-100 rounded w-1/3" />
                </div>
              </div>
            ))}
          </div>
        ) : uniquePatients.length === 0 ? (
          <div className="card p-12 flex flex-col items-center justify-center text-center gap-3">
            <div className="w-12 h-12 rounded-2xl bg-slate-100 flex items-center justify-center">
              <User size={22} className="text-slate-400" />
            </div>
            <p className="text-sm font-medium text-slate-600">No patients found</p>
          </div>
        ) : (
          <div className="space-y-3">
            {uniquePatients.map((apt) => {
              const patientApts = filtered.filter((a) => a.patient_id === apt.patient_id);
              const profile = profiles[apt.patient_id];
              const name = profile?.name ?? apt.patient_name ?? apt.patient_id;
              const age = calcAge(profile?.medical?.date_of_birth);
              const phone = profile?.phone;
              return (
                <div key={apt.patient_id} className="card p-4">
                  <div className="flex items-start gap-3">
                    <div className="w-10 h-10 rounded-xl bg-indigo-50 flex items-center justify-center shrink-0 border border-indigo-100">
                      <User size={16} className="text-indigo-500" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0">
                          <p className="text-sm font-semibold text-slate-800 truncate">{name}</p>
                          {(age !== null || phone) && (
                            <p className="text-xs text-slate-500">
                              {age !== null ? `${age} years old` : ""}
                              {age !== null && phone ? " • " : ""}
                              {phone ?? ""}
                            </p>
                          )}
                          {apt.specialty && (
                            <p className="text-xs text-slate-500">{apt.specialty}</p>
                          )}
                        </div>
                        <button
                          onClick={() => setSelected({ id: apt.patient_id, name })}
                          className="shrink-0 text-xs font-medium text-indigo-600 hover:text-indigo-700 px-2.5 py-1 rounded-lg hover:bg-indigo-50 transition-colors"
                        >
                          View Patient
                        </button>
                      </div>
                      <div className="mt-2.5 space-y-1.5">
                        {patientApts.map((a) => (
                          <div key={a.id} className="flex items-center gap-2 text-xs text-slate-500">
                            <CalendarDays size={11} className="shrink-0" />
                            <span>{formatDate(a.date)} · {formatTime(a.time)}</span>
                            <StatusBadge status={a.status} />
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
