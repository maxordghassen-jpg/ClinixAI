"use client";

import { useRef, useCallback } from "react";
import FullCalendar from "@fullcalendar/react";
import dayGridPlugin from "@fullcalendar/daygrid";
import timeGridPlugin from "@fullcalendar/timegrid";
import interactionPlugin from "@fullcalendar/interaction";
import type { EventInput, EventClickArg, DateSelectArg } from "@fullcalendar/core";

interface Props {
  events?: EventInput[];
  onEventClick?: (info: EventClickArg) => void;
  onDateSelect?: (info: DateSelectArg) => void;
  initialView?: "timeGridWeek" | "timeGridDay" | "dayGridMonth";
}

const STATUS_COLORS: Record<string, { bg: string; border: string; text: string }> = {
  confirmed: { bg: "#ecfdf5", border: "#10b981", text: "#065f46" },
  pending:   { bg: "#fffbeb", border: "#f59e0b", text: "#92400e" },
  cancelled: { bg: "#fff1f2", border: "#f43f5e", text: "#881337" },
  rejected:  { bg: "#fff1f2", border: "#f43f5e", text: "#881337" },
};

export function appointmentToEvent(apt: {
  id: string;
  date: string;
  time: string;
  end_time?: string;
  patient_name?: string;
  doctor_name?: string;
  specialty?: string;
  status: string;
}): EventInput {
  const colors = STATUS_COLORS[apt.status] ?? STATUS_COLORS.pending;
  const dateOnly = apt.date.slice(0, 10);
  const start = `${dateOnly}T${apt.time}`;
  const end = apt.end_time ? `${dateOnly}T${apt.end_time}` : undefined;

  return {
    id: apt.id,
    title: apt.patient_name ?? apt.doctor_name ?? "Appointment",
    start,
    end,
    backgroundColor: colors.bg,
    borderColor: colors.border,
    textColor: colors.text,
    extendedProps: { apt },
  };
}

export default function DoctorCalendar({ events = [], onEventClick, onDateSelect, initialView = "timeGridWeek" }: Props) {
  const calRef = useRef<FullCalendar>(null);

  const handleEventClick = useCallback((info: EventClickArg) => {
    onEventClick?.(info);
  }, [onEventClick]);

  const handleDateSelect = useCallback((info: DateSelectArg) => {
    onDateSelect?.(info);
  }, [onDateSelect]);

  return (
    <div className="fc-wrapper bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden p-4">
      <FullCalendar
        ref={calRef}
        plugins={[dayGridPlugin, timeGridPlugin, interactionPlugin]}
        initialView={initialView}
        headerToolbar={{
          left: "prev,next today",
          center: "title",
          right: "dayGridMonth,timeGridWeek,timeGridDay",
        }}
        events={events}
        selectable
        selectMirror
        dayMaxEvents
        weekends
        slotMinTime="07:00:00"
        slotMaxTime="21:00:00"
        slotDuration="00:30:00"
        height="auto"
        eventClick={handleEventClick}
        select={handleDateSelect}
        eventClassNames="rounded-lg text-xs font-medium cursor-pointer"
      />
    </div>
  );
}
