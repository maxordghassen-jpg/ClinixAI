"use client";

import { useState } from "react";
import { getDoctorAvailability, createAvailability, getFreeSlots } from "@/lib/api";
import type { Availability, AvailabilitySlot } from "@/types";

type Panel = "view" | "add" | "slots";

export default function AvailabilityPage() {
  const [activePanel, setActivePanel] = useState<Panel>("view");

  return (
    <div className="max-w-3xl mx-auto flex flex-col gap-4">
      <h1 className="text-xl font-semibold">Availability</h1>

      <div className="flex gap-2 flex-wrap">
        {(["view", "add", "slots"] as Panel[]).map((p) => (
          <button
            key={p}
            onClick={() => setActivePanel(p)}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              activePanel === p
                ? "bg-blue-600 text-white"
                : "bg-white border border-gray-300 text-gray-700 hover:bg-gray-50"
            }`}
          >
            {p === "view" && "View Availability"}
            {p === "add" && "Add Availability"}
            {p === "slots" && "Free Slots"}
          </button>
        ))}
      </div>

      {activePanel === "view" && <ViewPanel />}
      {activePanel === "add" && <AddPanel />}
      {activePanel === "slots" && <SlotsPanel />}
    </div>
  );
}

// ── View ──────────────────────────────────────────────────────────────────────

function ViewPanel() {
  const [doctorId, setDoctorId] = useState("");
  const [result, setResult] = useState<Availability[] | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const data = await getDoctorAvailability(doctorId.trim());
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4 flex flex-col gap-4">
      <h2 className="font-medium text-gray-700">View Doctor Availability</h2>
      <form onSubmit={submit} className="flex gap-3 items-end">
        <div className="flex-1">
          <Field label="Doctor ID" value={doctorId} onChange={setDoctorId} required />
        </div>
        <button
          type="submit"
          disabled={loading || !doctorId.trim()}
          className="rounded-lg bg-blue-600 text-white px-4 py-2 text-sm font-medium hover:bg-blue-700 disabled:opacity-40 transition-colors"
        >
          {loading ? "Loading…" : "Fetch"}
        </button>
      </form>
      {error && <p className="text-red-500 text-xs">{error}</p>}
      {result !== null && (
        result.length === 0 ? (
          <p className="text-gray-400 text-sm">No availability records found.</p>
        ) : (
          <div className="flex flex-col gap-3">
            {result.map((avail) => (
              <AvailabilityCard key={avail.id} avail={avail} />
            ))}
          </div>
        )
      )}
    </div>
  );
}

// ── Add ───────────────────────────────────────────────────────────────────────

function AddPanel() {
  const [doctorId, setDoctorId] = useState("");
  const [day, setDay] = useState("");
  const [slots, setSlots] = useState([{ start: "", end: "" }]);
  const [result, setResult] = useState<Availability | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  function addSlot() {
    setSlots((prev) => [...prev, { start: "", end: "" }]);
  }

  function removeSlot(idx: number) {
    setSlots((prev) => prev.filter((_, i) => i !== idx));
  }

  function updateSlot(idx: number, field: "start" | "end", value: string) {
    setSlots((prev) => prev.map((s, i) => (i === idx ? { ...s, [field]: value } : s)));
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const data = await createAvailability({ doctor_id: doctorId.trim(), day: day.trim(), slots });
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4 flex flex-col gap-4">
      <h2 className="font-medium text-gray-700">Add Availability</h2>
      <form onSubmit={submit} className="flex flex-col gap-3">
        <div className="grid grid-cols-2 gap-3">
          <Field label="Doctor ID" value={doctorId} onChange={setDoctorId} required />
          <Field label="Day (e.g. monday)" value={day} onChange={setDay} placeholder="monday" required />
        </div>

        <div className="flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <span className="text-xs text-gray-500">Time Slots</span>
            <button
              type="button"
              onClick={addSlot}
              className="text-xs text-blue-600 hover:underline"
            >
              + Add slot
            </button>
          </div>
          {slots.map((slot, idx) => (
            <div key={idx} className="flex gap-2 items-end">
              <div className="flex-1">
                <Field
                  label="Start (HH:MM)"
                  value={slot.start}
                  onChange={(v) => updateSlot(idx, "start", v)}
                  placeholder="08:00"
                  required
                />
              </div>
              <div className="flex-1">
                <Field
                  label="End (HH:MM)"
                  value={slot.end}
                  onChange={(v) => updateSlot(idx, "end", v)}
                  placeholder="09:00"
                  required
                />
              </div>
              {slots.length > 1 && (
                <button
                  type="button"
                  onClick={() => removeSlot(idx)}
                  className="mb-1 text-xs text-red-500 hover:underline"
                >
                  Remove
                </button>
              )}
            </div>
          ))}
        </div>

        <div>
          <button
            type="submit"
            disabled={loading}
            className="rounded-lg bg-blue-600 text-white px-4 py-2 text-sm font-medium hover:bg-blue-700 disabled:opacity-40 transition-colors"
          >
            {loading ? "Saving…" : "Save"}
          </button>
        </div>
      </form>
      {error && <p className="text-red-500 text-xs">{error}</p>}
      {result && (
        <div className="rounded-lg bg-gray-50 border border-gray-200 p-3 text-xs font-mono text-gray-700 overflow-x-auto whitespace-pre">
          {JSON.stringify(result, null, 2)}
        </div>
      )}
    </div>
  );
}

// ── Free Slots ────────────────────────────────────────────────────────────────

function SlotsPanel() {
  const [doctorId, setDoctorId] = useState("");
  const [date, setDate] = useState("");
  const [slots, setSlots] = useState<AvailabilitySlot[] | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    setSlots(null);
    try {
      const data = await getFreeSlots(doctorId.trim(), date.trim());
      setSlots(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4 flex flex-col gap-4">
      <h2 className="font-medium text-gray-700">Free Slots</h2>
      <form onSubmit={submit} className="grid grid-cols-2 gap-3">
        <Field label="Doctor ID" value={doctorId} onChange={setDoctorId} required />
        <Field label="Date (YYYY-MM-DD)" value={date} onChange={setDate} placeholder="2026-05-22" required />
        <div className="col-span-2">
          <button
            type="submit"
            disabled={loading || !doctorId.trim() || !date.trim()}
            className="rounded-lg bg-blue-600 text-white px-4 py-2 text-sm font-medium hover:bg-blue-700 disabled:opacity-40 transition-colors"
          >
            {loading ? "Loading…" : "Get Free Slots"}
          </button>
        </div>
      </form>
      {error && <p className="text-red-500 text-xs">{error}</p>}
      {slots !== null && (
        slots.length === 0 ? (
          <p className="text-gray-400 text-sm">No free slots available.</p>
        ) : (
          <div className="flex flex-col gap-2">
            {slots.map((slot, idx) => (
              <div
                key={idx}
                className="flex items-center gap-3 rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-sm"
              >
                <span className="font-medium text-gray-700">{slot.start} – {slot.end}</span>
                <span
                  className={`ml-auto text-xs font-medium px-2 py-0.5 rounded-full ${
                    slot.status === "free"
                      ? "bg-green-100 text-green-700"
                      : "bg-red-100 text-red-700"
                  }`}
                >
                  {slot.status}
                </span>
              </div>
            ))}
          </div>
        )
      )}
    </div>
  );
}

// ── Shared ────────────────────────────────────────────────────────────────────

function AvailabilityCard({ avail }: { avail: Availability }) {
  return (
    <div className="rounded-lg border border-gray-200 p-3 flex flex-col gap-2">
      <div className="flex items-center gap-2">
        <span className="font-medium text-sm capitalize">{avail.day}</span>
        <span className="text-xs text-gray-400">· {avail.doctor_id}</span>
      </div>
      <div className="flex flex-wrap gap-2">
        {avail.slots.map((slot, idx) => (
          <span
            key={idx}
            className={`text-xs px-2 py-0.5 rounded-full ${
              slot.status === "free"
                ? "bg-green-100 text-green-700"
                : "bg-gray-100 text-gray-500"
            }`}
          >
            {slot.start}–{slot.end}
          </span>
        ))}
      </div>
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
