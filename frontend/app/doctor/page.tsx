"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { CalendarDays, Users, Clock, CheckCircle, X } from "lucide-react";
import StatCard from "@/components/ui/StatCard";
import AppointmentCard from "@/components/appointments/AppointmentCard";
import ChatPanel from "@/components/chat/ChatPanel";
import TopBar from "@/components/layout/TopBar";
import MedicalProfileSummary from "@/components/profile/MedicalProfileSummary";
import { useDoctorChatStore } from "@/stores/doctor/useChatStore";
import { useIdentity } from "@/hooks/useIdentity";
import { useVoice } from "@/hooks/useVoice";
import { getDoctorTodayAppointments, getDoctorWeekAppointments, confirmAppointment, cancelAppointment } from "@/services/api/appointments";
import { doctorChat, getAppointmentReport } from "@/lib/api";
import { getGreeting } from "@/lib/utils";
import type { Appointment, PreConsultationReport } from "@/types";
import ReportPanel from "@/components/doctor/ReportPanel";

export default function DoctorDashboard() {
  const { user, doctorId, sessionId } = useIdentity();

  const [todayApts, setTodayApts]     = useState<Appointment[]>([]);
  const [weekApts, setWeekApts]       = useState<Appointment[]>([]);
  const [loadingApts, setLoadingApts] = useState(true);
  const [selectedApt, setSelectedApt] = useState<Appointment | null>(null);

  const [reportApt, setReportApt]         = useState<Appointment | null>(null);
  const [reportData, setReportData]       = useState<PreConsultationReport | null>(null);
  const [reportLoading, setReportLoading] = useState(false);

  const { messages, isLoading, isOpen, addMessage, setLoading, togglePanel, clearMessages } = useDoctorChatStore();

  // ── Voice layer ────────────────────────────────────────────────────────────
  const [sessionLang, setSessionLang] = useState<string | undefined>();
  const speakRef = useRef<(text: string) => void>(() => {});

  // ── Appointments ───────────────────────────────────────────────────────────

  const fetchAppointments = useCallback(async () => {
    if (!doctorId) return;
    setLoadingApts(true);
    try {
      const [today, week] = await Promise.all([
        getDoctorTodayAppointments(doctorId).catch(() => []),
        getDoctorWeekAppointments(doctorId).catch(() => []),
      ]);
      setTodayApts(today);
      setWeekApts(week);
    } finally {
      setLoadingApts(false);
    }
  }, [doctorId]);

  useEffect(() => { fetchAppointments(); }, [fetchAppointments]);

  // ── Chat handler ───────────────────────────────────────────────────────────

  async function handleSend(text: string) {
    const ts = new Date().toLocaleTimeString();
    addMessage({ role: "user", content: text, timestamp: ts });
    setLoading(true);
    try {
      const res = await doctorChat({
        message:    text,
        session_id: sessionId || undefined,
        doctor_id:  doctorId  || undefined,
      });

      const reply = res.response ?? "(no response)";
      addMessage({ role: "assistant", content: reply, timestamp: new Date().toLocaleTimeString() });

      // Update voice language if backend returns one
      const detectedLang = (res.memory as Record<string, unknown> | undefined)?.language;
      if (typeof detectedLang === "string") setSessionLang(detectedLang);

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

  const voice = useVoice({
    language:     sessionLang,
    onTranscript: handleSend,
    autoSpeak:    true,
  });

  useEffect(() => {
    speakRef.current = voice.speakResponse;
  }, [voice.speakResponse]);

  // ── Appointment helpers ────────────────────────────────────────────────────

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

  const pendingCount   = weekApts.filter((a) => a.status === "pending").length;
  const confirmedCount = weekApts.filter((a) => a.status === "confirmed").length;

  const stats = [
    { label: "Today's Appointments",  value: todayApts.length,  icon: CalendarDays, color: "indigo" as const },
    { label: "This Week",             value: weekApts.length,   icon: Clock,        color: "teal"   as const },
    { label: "Awaiting Confirmation", value: pendingCount,      icon: Users,        color: "amber"  as const },
    { label: "Confirmed This Week",   value: confirmedCount,    icon: CheckCircle,  color: "violet" as const },
  ];

  return (
    <div className="flex flex-col min-h-full">
      <TopBar
        title={`${getGreeting()}${user?.name ? `, ${user.name}` : ", Doctor"}`}
        subtitle="Here's your schedule overview"
      />

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

      <div className="flex-1 p-6 space-y-6">
        {/* Stats */}
        <div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
          {stats.map((s) => (
            <StatCard key={s.label} {...s} />
          ))}
        </div>

        {/* Main content grid */}
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
          {/* Today's appointments */}
          <div className="xl:col-span-2 space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold text-slate-700">Today's Appointments</h2>
              <a href="/doctor/appointments" className="text-xs text-indigo-600 hover:text-indigo-700 font-medium">
                View all
              </a>
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
            ) : todayApts.length === 0 ? (
              <div className="card p-8 flex flex-col items-center justify-center text-center gap-3">
                <div className="w-12 h-12 rounded-2xl bg-slate-100 flex items-center justify-center">
                  <CalendarDays size={22} className="text-slate-400" />
                </div>
                <div>
                  <p className="text-sm font-medium text-slate-600">No appointments today</p>
                  <p className="text-xs text-slate-400 mt-0.5">Your schedule is clear for today</p>
                </div>
              </div>
            ) : (
              <div className="space-y-3">
                {todayApts.map((apt) => (
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

            {/* Upcoming this week */}
            {weekApts.length > todayApts.length && (
              <div className="space-y-3 mt-6">
                <h2 className="text-sm font-semibold text-slate-700">Upcoming This Week</h2>
                <div className="space-y-3">
                  {weekApts
                    .filter((a) => !todayApts.some((t) => t.id === a.id))
                    .map((apt) => (
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
              </div>
            )}
          </div>

          {/* AI Assistant */}
          <div className="xl:col-span-1">
            <ChatPanel
              title="Doctor AI Assistant"
              placeholder="Ask about your schedule, patients…"
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
