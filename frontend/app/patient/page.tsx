"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { CalendarDays, Clock, CheckCircle, UserSearch } from "lucide-react";
import StatCard from "@/components/ui/StatCard";
import AppointmentCard from "@/components/appointments/AppointmentCard";
import ChatPanel from "@/components/chat/ChatPanel";
import TopBar from "@/components/layout/TopBar";
import { usePatientChatStore } from "@/stores/patient/useChatStore";
import { useOrchestrationStore } from "@/stores/useOrchestrationStore";
import { useAIOrchestration } from "@/hooks/useAIOrchestration";
import { useGeolocation } from "@/hooks/useGeolocation";
import { useIdentity } from "@/hooks/useIdentity";
import { useVoice } from "@/hooks/useVoice";
import { getPatientWeekAppointments, cancelAppointment } from "@/services/api/appointments";
import { patientChat } from "@/lib/api";
import { getGreeting, getRelativeDay } from "@/lib/utils";
import type { Appointment } from "@/types";

export default function PatientDashboard() {
  const { patientId, sessionId, user } = useIdentity();
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [loadingApts, setLoadingApts]   = useState(true);

  const { messages, isLoading, isOpen, addMessage, setLoading, togglePanel, clearMessages } = usePatientChatStore();
  const { handleAIResponse } = useAIOrchestration();
  const { userLocation } = useOrchestrationStore();
  useGeolocation();

  // ── Voice layer ────────────────────────────────────────────────────────────
  // `sessionLang` mirrors the backend-detected language from the last AI response.
  // It is passed to useVoice so STT/TTS use the correct locale.
  const [sessionLang, setSessionLang] = useState<string | undefined>();

  // speakRef breaks the circular dep: handleSend calls speakRef.current which
  // points to voice.speakResponse — set after the hook is initialised below.
  const speakRef = useRef<(text: string) => void>(() => {});

  // ── Appointments ───────────────────────────────────────────────────────────

  const fetchAppointments = useCallback(async () => {
    if (!patientId) return;
    setLoadingApts(true);
    try {
      const apts = await getPatientWeekAppointments(patientId).catch(() => []);
      setAppointments(apts);
    } finally {
      setLoadingApts(false);
    }
  }, [patientId]);

  useEffect(() => { fetchAppointments(); }, [fetchAppointments]);

  // ── Chat handler ───────────────────────────────────────────────────────────

  async function handleSend(text: string) {
    const ts = new Date().toLocaleTimeString();
    addMessage({ role: "user", content: text, timestamp: ts });
    setLoading(true);
    try {
      const res = await patientChat({
        message:    text,
        session_id: sessionId ?? undefined,
        patient_id: patientId ?? undefined,
        latitude:   userLocation?.lat,
        longitude:  userLocation?.lng,
      });

      const reply = res.response ?? "(no response)";
      addMessage({ role: "assistant", content: reply, timestamp: new Date().toLocaleTimeString() });
      handleAIResponse(res as Parameters<typeof handleAIResponse>[0]);

      // Update voice language from backend detection
      const detectedLang = (res.memory as Record<string, unknown> | undefined)?.language;
      if (typeof detectedLang === "string") setSessionLang(detectedLang);

      // Speak the reply if the user used voice for this turn
      speakRef.current(reply);
    } catch (err) {
      addMessage({
        role:      "assistant",
        content:   err instanceof Error ? err.message : "Something went wrong",
        timestamp: new Date().toLocaleTimeString(),
      });
    } finally {
      setLoading(false);
    }
  }

  // ── Voice hook ─────────────────────────────────────────────────────────────
  // Initialised after handleSend is declared (function declarations are hoisted,
  // so useVoice can safely capture handleSend via its internal ref).

  const voice = useVoice({
    language:     sessionLang,
    onTranscript: handleSend,
    autoSpeak:    true,
  });

  // Keep speakRef pointing to the latest speakResponse
  useEffect(() => {
    speakRef.current = voice.speakResponse;
  }, [voice.speakResponse]);

  // ── Appointment helpers ────────────────────────────────────────────────────

  async function handleCancel(id: string) {
    await cancelAppointment(id).catch(console.error);
    fetchAppointments();
  }

  const upcoming  = appointments.filter((a) => a.status !== "cancelled" && a.status !== "rejected");
  const confirmed = appointments.filter((a) => a.status === "confirmed");
  const pending   = appointments.filter((a) => a.status === "pending");
  const nextApt   = upcoming.sort((a, b) => a.date.localeCompare(b.date))[0];

  const stats = [
    { label: "Appointments This Week", value: upcoming.length,  icon: CalendarDays, color: "indigo" as const },
    { label: "Confirmed",              value: confirmed.length, icon: CheckCircle,  color: "teal"   as const },
    { label: "Awaiting Confirmation",  value: pending.length,   icon: Clock,        color: "amber"  as const },
    { label: "Next Appointment",       value: nextApt ? getRelativeDay(nextApt.date) : "—", icon: UserSearch, color: "violet" as const },
  ];

  return (
    <div className="flex flex-col min-h-full">
      <TopBar
        title={`${getGreeting()}${user?.name ? `, ${user.name}` : ""}`}
        subtitle="How can we help you today?"
      />

      <div className="flex-1 p-6 space-y-6">
        <div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
          {stats.map((s) => (
            <StatCard key={s.label} {...s} />
          ))}
        </div>

        <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
          <div className="xl:col-span-2 space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold text-slate-700">Upcoming Appointments</h2>
              <a href="/patient/appointments" className="text-xs text-indigo-600 hover:text-indigo-700 font-medium">View all</a>
            </div>

            {loadingApts ? (
              <div className="space-y-3">
                {[1, 2, 3].map((i) => (
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
            ) : upcoming.length === 0 ? (
              <div className="card p-10 flex flex-col items-center justify-center text-center gap-4">
                <div className="w-14 h-14 rounded-2xl bg-indigo-50 flex items-center justify-center">
                  <CalendarDays size={24} className="text-indigo-400" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-slate-700">No upcoming appointments</p>
                  <p className="text-xs text-slate-400 mt-1">Ask the AI assistant to book one for you</p>
                </div>
                <button onClick={togglePanel} className="btn-primary text-sm px-5 py-2">
                  Book an appointment
                </button>
              </div>
            ) : (
              <div className="space-y-3">
                {upcoming.map((apt) => (
                  <AppointmentCard key={apt.id} appointment={apt} role="patient" onCancel={handleCancel} />
                ))}
              </div>
            )}

            <div className="grid grid-cols-2 gap-3 mt-4">
              <a href="/patient/doctors" className="card p-4 flex items-center gap-3 hover:border-indigo-200 hover:bg-indigo-50/30 transition-all cursor-pointer group">
                <div className="w-9 h-9 rounded-xl bg-indigo-50 flex items-center justify-center shrink-0 border border-indigo-100">
                  <UserSearch size={16} className="text-indigo-500" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-slate-800">Find a Doctor</p>
                  <p className="text-xs text-slate-500">Search by specialty</p>
                </div>
              </a>
              <a href="/patient/map" className="card p-4 flex items-center gap-3 hover:border-teal-200 hover:bg-teal-50/30 transition-all cursor-pointer group">
                <div className="w-9 h-9 rounded-xl bg-teal-50 flex items-center justify-center shrink-0 border border-teal-100">
                  <CalendarDays size={16} className="text-teal-500" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-slate-800">Nearby Clinics</p>
                  <p className="text-xs text-slate-500">Find clinics on map</p>
                </div>
              </a>
            </div>
          </div>

          <div className="xl:col-span-1">
            <ChatPanel
              title="Patient AI Assistant"
              placeholder="Book an appointment, find a doctor…"
              messages={messages}
              isLoading={isLoading}
              isOpen={isOpen}
              onToggle={togglePanel}
              onSend={handleSend}
              onClear={clearMessages}
              voice={{
                voiceState:  voice.voiceState,
                transcript:  voice.transcript,
                isSupported: voice.isSupported,
                error:       voice.error,
                onToggle:    voice.toggleMic,
                onStop:      voice.stopSpeaking,
              }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
