"use client";

import { useState } from "react";
import {
  createAppointment,
  cancelAppointment,
  rescheduleAppointment,
  getPatientAppointmentsWeek,
} from "@/lib/api";
import type { Appointment } from "@/types";

type Panel = "create" | "cancel" | "reschedule" | "list";

export default function AppointmentsPage() {
  const [activePanel, setActivePanel] = useState<Panel>("create");

  return (
    <div className="max-w-3xl mx-auto flex flex-col gap-4">
      <h1 className="text-xl font-semibold">Appointments</h1>

      <div className="flex gap-2 flex-wrap">
        {(["create", "cancel", "reschedule", "list"] as Panel[]).map((p) => (
          <button
            key={p}
            onClick={() => setActivePanel(p)}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              activePanel === p
                ? "bg-blue-600 text-white"
                : "bg-white border border-gray-300 text-gray-700 hover:bg-gray-50"
            }`}
          >
            {p === "create" && "Create"}
            {p === "cancel" && "Cancel"}
            {p === "reschedule" && "Reschedule"}
            {p === "list" && "List (week)"}
          </button>
        ))}
      </div>

      {activePanel === "create" && <CreatePanel />}
      {activePanel === "cancel" && <CancelPanel />}
      {activePanel === "reschedule" && <ReschedulePanel />}
      {activePanel === "list" && <ListPanel />}
    </div>
  );
}

// ── Create ────────────────────────────────────────────────────────────────────

function CreatePanel() {
  const [doctorId, setDoctorId] = useState("");
  const [patientId, setPatientId] = useState("");
  const [date, setDate] = useState("");
  const [time, setTime] = useState("");
  const [result, setResult] = useState<Appointment | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const appt = await createAppointment({ doctor_id: doctorId, patient_id: patientId, date, time });
      setResult(appt);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4 flex flex-col gap-4">
      <h2 className="font-medium text-gray-700">Create Appointment</h2>
      <form onSubmit={submit} className="grid grid-cols-2 gap-3">
        <Field label="Doctor ID" value={doctorId} onChange={setDoctorId} required />
        <Field label="Patient ID" value={patientId} onChange={setPatientId} required />
        <Field label="Date (YYYY-MM-DD)" value={date} onChange={setDate} placeholder="2026-05-22" required />
        <Field label="Time (HH:MM)" value={time} onChange={setTime} placeholder="09:00" required />
        <div className="col-span-2">
          <button
            type="submit"
            disabled={loading}
            className="rounded-lg bg-blue-600 text-white px-4 py-2 text-sm font-medium hover:bg-blue-700 disabled:opacity-40 transition-colors"
          >
            {loading ? "Creating…" : "Create"}
          </button>
        </div>
      </form>
      {error && <p className="text-red-500 text-xs">{error}</p>}
      {result && <ResultCard data={result} />}
    </div>
  );
}

// ── Cancel ────────────────────────────────────────────────────────────────────

function CancelPanel() {
  const [appointmentId, setAppointmentId] = useState("");
  const [result, setResult] = useState<Appointment | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const appt = await cancelAppointment(appointmentId.trim());
      setResult(appt);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4 flex flex-col gap-4">
      <h2 className="font-medium text-gray-700">Cancel Appointment</h2>
      <form onSubmit={submit} className="flex gap-3 items-end">
        <div className="flex-1">
          <Field label="Appointment ID" value={appointmentId} onChange={setAppointmentId} required />
        </div>
        <button
          type="submit"
          disabled={loading || !appointmentId.trim()}
          className="rounded-lg bg-red-600 text-white px-4 py-2 text-sm font-medium hover:bg-red-700 disabled:opacity-40 transition-colors"
        >
          {loading ? "Cancelling…" : "Cancel"}
        </button>
      </form>
      {error && <p className="text-red-500 text-xs">{error}</p>}
      {result && <ResultCard data={result} />}
    </div>
  );
}

// ── Reschedule ────────────────────────────────────────────────────────────────

function ReschedulePanel() {
  const [appointmentId, setAppointmentId] = useState("");
  const [date, setDate] = useState("");
  const [time, setTime] = useState("");
  const [result, setResult] = useState<Appointment | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const appt = await rescheduleAppointment(appointmentId.trim(), { date, time });
      setResult(appt);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4 flex flex-col gap-4">
      <h2 className="font-medium text-gray-700">Reschedule Appointment</h2>
      <form onSubmit={submit} className="grid grid-cols-2 gap-3">
        <div className="col-span-2">
          <Field label="Appointment ID" value={appointmentId} onChange={setAppointmentId} required />
        </div>
        <Field label="New Date (YYYY-MM-DD)" value={date} onChange={setDate} placeholder="2026-05-25" required />
        <Field label="New Time (HH:MM)" value={time} onChange={setTime} placeholder="10:30" required />
        <div className="col-span-2">
          <button
            type="submit"
            disabled={loading || !appointmentId.trim()}
            className="rounded-lg bg-blue-600 text-white px-4 py-2 text-sm font-medium hover:bg-blue-700 disabled:opacity-40 transition-colors"
          >
            {loading ? "Rescheduling…" : "Reschedule"}
          </button>
        </div>
      </form>
      {error && <p className="text-red-500 text-xs">{error}</p>}
      {result && <ResultCard data={result} />}
    </div>
  );
}

// ── List ──────────────────────────────────────────────────────────────────────

function ListPanel() {
  const [patientId, setPatientId] = useState("");
  const [appointments, setAppointments] = useState<Appointment[] | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    setAppointments(null);
    try {
      const list = await getPatientAppointmentsWeek(patientId.trim());
      setAppointments(list);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4 flex flex-col gap-4">
      <h2 className="font-medium text-gray-700">Patient Appointments (This Week)</h2>
      <form onSubmit={submit} className="flex gap-3 items-end">
        <div className="flex-1">
          <Field label="Patient ID" value={patientId} onChange={setPatientId} required />
        </div>
        <button
          type="submit"
          disabled={loading || !patientId.trim()}
          className="rounded-lg bg-blue-600 text-white px-4 py-2 text-sm font-medium hover:bg-blue-700 disabled:opacity-40 transition-colors"
        >
          {loading ? "Loading…" : "Fetch"}
        </button>
      </form>
      {error && <p className="text-red-500 text-xs">{error}</p>}
      {appointments !== null && (
        appointments.length === 0 ? (
          <p className="text-gray-400 text-sm">No appointments found.</p>
        ) : (
          <div className="flex flex-col gap-2">
            {appointments.map((a) => (
              <ResultCard key={a.id} data={a} />
            ))}
          </div>
        )
      )}
    </div>
  );
}

// ── Shared ────────────────────────────────────────────────────────────────────

function ResultCard({ data }: { data: Appointment }) {
  return (
    <div className="rounded-lg bg-gray-50 border border-gray-200 p-3 text-xs font-mono text-gray-700 overflow-x-auto whitespace-pre">
      {JSON.stringify(data, null, 2)}
    </div>
  );
}

function Field({
  label, value, onChange, placeholder, required,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  required?: boolean;
}) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-xs text-gray-500">{label}</span>
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        required={required}
        className="rounded border border-gray-300 px-2 py-1 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
      />
    </label>
  );
}
