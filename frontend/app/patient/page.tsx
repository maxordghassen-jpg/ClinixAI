"use client";

import { useState, useRef, FormEvent } from "react";
import ChatWindow from "@/components/ChatWindow";
import { patientChat } from "@/lib/api";
import type { Message } from "@/types";

export default function PatientChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Session config
  const [sessionId, setSessionId] = useState("session-001");
  const [patientId, setPatientId] = useState("patient-001");
  const [doctorId, setDoctorId] = useState("");

  const [input, setInput] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  async function send(e: FormEvent) {
    e.preventDefault();
    const msg = input.trim();
    if (!msg) return;

    const ts = new Date().toLocaleTimeString();
    setMessages((prev) => [...prev, { role: "user", content: msg, timestamp: ts }]);
    setInput("");
    setLoading(true);
    setError("");

    try {
      const res = await patientChat({
        message: msg,
        session_id: sessionId || undefined,
        patient_id: patientId || undefined,
        doctor_id: doctorId || undefined,
      });

      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: res.response ?? "(no response)",
          timestamp: new Date().toLocaleTimeString(),
        },
      ]);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Request failed";
      setError(msg);
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  }

  return (
    <div className="max-w-3xl mx-auto flex flex-col gap-4">
      <h1 className="text-xl font-semibold">Patient Chat</h1>

      {/* Session config */}
      <div className="grid grid-cols-3 gap-3 bg-white rounded-lg border border-gray-200 p-4">
        <Field label="Session ID" value={sessionId} onChange={setSessionId} />
        <Field label="Patient ID" value={patientId} onChange={setPatientId} />
        <Field label="Doctor ID (opt)" value={doctorId} onChange={setDoctorId} />
      </div>

      {/* Chat */}
      <div className="bg-white rounded-lg border border-gray-200 flex flex-col gap-3 p-4" style={{ height: "60vh" }}>
        <ChatWindow messages={messages} loading={loading} />

        {error && (
          <p className="text-red-500 text-xs px-1">{error}</p>
        )}

        <form onSubmit={send} className="flex gap-2">
          <input
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Type a message…"
            disabled={loading}
            className="flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="rounded-lg bg-blue-600 text-white px-4 py-2 text-sm font-medium hover:bg-blue-700 disabled:opacity-40 transition-colors"
          >
            Send
          </button>
          <button
            type="button"
            onClick={() => setMessages([])}
            className="rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-600 hover:bg-gray-50 transition-colors"
          >
            Clear
          </button>
        </form>
      </div>
    </div>
  );
}

function Field({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-xs text-gray-500">{label}</span>
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="rounded border border-gray-300 px-2 py-1 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
      />
    </label>
  );
}
