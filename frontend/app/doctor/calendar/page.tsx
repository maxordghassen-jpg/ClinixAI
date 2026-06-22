"use client";

import dynamic from "next/dynamic";
import { useEffect, useState, useCallback } from "react";
import type { EventInput, EventClickArg } from "@fullcalendar/core";
import TopBar from "@/components/layout/TopBar";
import { appointmentToEvent } from "@/components/calendar/DoctorCalendar";
import { getDoctorWeekAppointments } from "@/services/api/appointments";
import { useIdentity } from "@/hooks/useIdentity";
import type { Appointment } from "@/types";
import { formatDate, formatTime } from "@/lib/utils";
import StatusBadge from "@/components/appointments/StatusBadge";

const DoctorCalendar = dynamic(() => import("@/components/calendar/DoctorCalendar"), { ssr: false });

export default function DoctorCalendarPage() {
  const { doctorId } = useIdentity();
  const [events, setEvents]   = useState<EventInput[]>([]);
  const [selected, setSelected] = useState<Appointment | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchEvents = useCallback(async () => {
    if (!doctorId) return;
    setLoading(true);
    try {
      const apts = await getDoctorWeekAppointments(doctorId).catch(() => []);
      setEvents(apts.map(appointmentToEvent));
    } finally {
      setLoading(false);
    }
  }, [doctorId]);

  useEffect(() => { fetchEvents(); }, [fetchEvents]);

  function handleEventClick(info: EventClickArg) {
    const apt = info.event.extendedProps.apt as Appointment;
    setSelected(apt);
  }

  return (
    <div className="flex flex-col min-h-full">
      <TopBar title="Calendar" subtitle="Manage your schedule" />

      <div className="flex-1 p-6 gap-6 flex flex-col xl:flex-row">
        <div className="flex-1 min-w-0">
          {loading ? (
            <div className="card p-8 flex items-center justify-center h-96">
              <div className="flex flex-col items-center gap-3">
                <div className="w-8 h-8 border-2 border-indigo-400 border-t-transparent rounded-full animate-spin" />
                <p className="text-sm text-slate-500">Loading schedule…</p>
              </div>
            </div>
          ) : (
            <DoctorCalendar events={events} onEventClick={handleEventClick} />
          )}
        </div>

        {/* Detail panel */}
        {selected && (
          <div className="xl:w-72 shrink-0">
            <div className="card p-5 space-y-4">
              <div className="flex items-start justify-between">
                <h3 className="text-sm font-semibold text-slate-800">Appointment Detail</h3>
                <button
                  onClick={() => setSelected(null)}
                  className="text-slate-400 hover:text-slate-600 text-xs"
                >
                  ✕
                </button>
              </div>
              <div className="space-y-2 text-sm">
                <p className="font-medium text-slate-800">{selected.patient_name ?? "—"}</p>
                <StatusBadge status={selected.status} />
                <div className="text-xs text-slate-500 space-y-1 mt-2">
                  <p>{formatDate(selected.date)}</p>
                  <p>{formatTime(selected.time)}{selected.end_time ? ` — ${formatTime(selected.end_time)}` : ""}</p>
                  {selected.specialty && <p>{selected.specialty}</p>}
                  {selected.notes && <p className="text-slate-400">{selected.notes}</p>}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
