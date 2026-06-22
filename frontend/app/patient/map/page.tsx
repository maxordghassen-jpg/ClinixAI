"use client";

import dynamic from "next/dynamic";
import { useState, useCallback, useEffect } from "react";
import { Search, MapPin, Star, Phone, Navigation, X, ChevronRight, Sparkles, SlidersHorizontal } from "lucide-react";
import TopBar from "@/components/layout/TopBar";
import ChatPanel from "@/components/chat/ChatPanel";
import { usePatientChatStore } from "@/stores/patient/useChatStore";
import { useOrchestrationStore } from "@/stores/useOrchestrationStore";
import { useAIOrchestration } from "@/hooks/useAIOrchestration";
import { useGeolocation } from "@/hooks/useGeolocation";
import { useIdentity } from "@/hooks/useIdentity";
import { patientChat } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { DoctorPin } from "@/types/orchestration";

const MapClient = dynamic(() => import("@/components/map/MapClient"), { ssr: false });

/* ── Specialty filter chips ─────────────────────────────────────────────── */
const SPECIALTIES = ["All", "Cardiologist", "Dermatologist", "Neurologist", "Dentist", "Pediatrician", "Ophthalmologist", "Pharmacy"];

/* ── Doctor detail sidebar card ─────────────────────────────────────────── */
function DoctorDetailCard({
  doctor,
  onClose,
  onBook,
}: {
  doctor: DoctorPin;
  onClose: () => void;
  onBook: (d: DoctorPin) => void;
}) {
  return (
    <div className="absolute bottom-4 left-1/2 -translate-x-1/2 z-[1000] w-full max-w-sm px-4">
      <div className="bg-white rounded-2xl shadow-xl border border-slate-200 p-4 animate-in slide-in-from-bottom-4 duration-200">
        <div className="flex items-start justify-between gap-2 mb-3">
          <div className="flex-1 min-w-0">
            <p className="font-semibold text-slate-800 truncate">{doctor.name}</p>
            {doctor.specialty && (
              <p className="text-xs text-indigo-600 font-medium capitalize mt-0.5">{doctor.specialty}</p>
            )}
          </div>
          <button onClick={onClose} className="p-1 rounded-lg hover:bg-slate-100 transition-colors shrink-0">
            <X size={14} className="text-slate-400" />
          </button>
        </div>

        <div className="space-y-1.5 mb-4">
          {doctor.address && (
            <div className="flex items-center gap-1.5 text-xs text-slate-500">
              <MapPin size={11} className="shrink-0" />
              <span className="truncate">{doctor.address}</span>
            </div>
          )}
          {doctor.phone && (
            <div className="flex items-center gap-1.5 text-xs text-slate-500">
              <Phone size={11} className="shrink-0" />
              {doctor.phone}
            </div>
          )}
          {doctor.rating !== undefined && (
            <div className="flex items-center gap-1 text-xs text-amber-600 font-medium">
              <Star size={11} className="fill-amber-400 text-amber-400" />
              {doctor.rating.toFixed(1)}
            </div>
          )}
          {doctor.is_open_now !== undefined && (
            <p className={cn("text-xs font-semibold", doctor.is_open_now ? "text-emerald-600" : "text-slate-400")}>
              {doctor.is_open_now ? "● Open now" : "● Closed"}
            </p>
          )}
        </div>

        <div className="flex gap-2">
          <button
            onClick={() => onBook(doctor)}
            className="flex-1 flex items-center justify-center gap-1.5 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold transition-colors shadow-md shadow-indigo-200"
          >
            Book Appointment
          </button>
          <button className="p-2 rounded-xl border border-slate-200 hover:bg-slate-50 transition-colors">
            <Navigation size={14} className="text-slate-500" />
          </button>
        </div>
      </div>
    </div>
  );
}

/* ── Results sidebar ──────────────────────────────────────────────────────── */
function ResultsSidebar({
  pins,
  selectedId,
  filters,
  onSelectPin,
  onSpecialtyFilter,
  isOpen,
}: {
  pins: DoctorPin[];
  selectedId: string | null;
  filters: { specialty?: string; query?: string };
  onSelectPin: (p: DoctorPin) => void;
  onSpecialtyFilter: (s: string) => void;
  isOpen: boolean;
}) {
  const activeSpecialty = filters.specialty ?? "All";

  if (!isOpen) return null;

  return (
    <div className="w-72 shrink-0 bg-white border-r border-slate-200 flex flex-col overflow-hidden">
      {/* Filter chips */}
      <div className="px-3 pt-3 pb-2 border-b border-slate-100">
        <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wide mb-2">Filter by specialty</p>
        <div className="flex flex-wrap gap-1.5">
          {SPECIALTIES.map((s) => (
            <button
              key={s}
              onClick={() => onSpecialtyFilter(s === "All" ? "" : s.toLowerCase())}
              className={cn(
                "text-[10px] font-semibold px-2 py-1 rounded-full border transition-colors",
                (s === "All" && !activeSpecialty) || activeSpecialty?.toLowerCase() === s.toLowerCase()
                  ? "bg-indigo-600 text-white border-indigo-600"
                  : "bg-white text-slate-600 border-slate-200 hover:border-indigo-300"
              )}
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      {/* Result list */}
      <div className="flex-1 overflow-y-auto">
        {pins.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full gap-3 p-6 text-center">
            <MapPin size={24} className="text-slate-300" />
            <div>
              <p className="text-sm font-medium text-slate-600">No results yet</p>
              <p className="text-xs text-slate-400 mt-0.5">Ask the AI assistant to find doctors near you</p>
            </div>
          </div>
        ) : (
          <div className="p-2 space-y-1">
            <p className="text-xs text-slate-400 px-2 py-1">{pins.length} result{pins.length !== 1 ? "s" : ""}</p>
            {pins.map((pin) => (
              <button
                key={pin.id}
                onClick={() => onSelectPin(pin)}
                className={cn(
                  "w-full text-left flex items-start gap-3 p-2.5 rounded-xl transition-all",
                  selectedId === pin.id
                    ? "bg-indigo-50 border border-indigo-200"
                    : "hover:bg-slate-50 border border-transparent"
                )}
              >
                <div className="w-8 h-8 rounded-lg bg-indigo-50 flex items-center justify-center shrink-0 border border-indigo-100 mt-0.5">
                  <MapPin size={13} className="text-indigo-500" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-slate-800 truncate leading-tight">{pin.name}</p>
                  {pin.specialty && (
                    <p className="text-[10px] text-indigo-600 font-medium capitalize mt-0.5">{pin.specialty}</p>
                  )}
                  {pin.address && (
                    <p className="text-[10px] text-slate-400 truncate mt-0.5">{pin.address}</p>
                  )}
                </div>
                <ChevronRight size={12} className="text-slate-300 shrink-0 mt-1" />
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

/* ── Page ─────────────────────────────────────────────────────────────────── */

export default function PatientMapPage() {
  const [selectedDoctor, setSelectedDoctor] = useState<DoctorPin | null>(null);
  const [chatOpen, setChatOpen] = useState(true);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [localSpecialtyFilter, setLocalSpecialtyFilter] = useState("");

  useGeolocation(); // request browser location; writes to orchestration store on grant

  const {
    mapPins, mapFilters, setMapFilters, setPendingBooking, userLocation,
  } = useOrchestrationStore();

  /* Debug: log pin count from store every time it changes */
  useEffect(() => {
    console.log("[MAP FLOW] stored pins from Zustand", mapPins.length, mapPins);
  }, [mapPins]);

  const { handleAIResponse } = useAIOrchestration();

  const { patientId, sessionId } = useIdentity();
  const {
    messages, isLoading, isOpen: chatIsOpen,
    addMessage, setLoading, togglePanel, clearMessages,
  } = usePatientChatStore();

  /* Filter pins by local specialty chip selection */
  const visiblePins = localSpecialtyFilter
    ? mapPins.filter((p) => p.specialty?.toLowerCase().includes(localSpecialtyFilter.toLowerCase()))
    : mapPins;

  async function handleSend(text: string) {
    const ts = new Date().toLocaleTimeString();
    addMessage({ role: "user", content: text, timestamp: ts });
    setLoading(true);
    try {
      const res = await patientChat({
        message: text,
        session_id: sessionId || undefined,
        patient_id: patientId || undefined,
        latitude:  userLocation?.lat,
        longitude: userLocation?.lng,
      });
      addMessage({
        role: "assistant",
        content: res.response ?? "(no response)",
        timestamp: new Date().toLocaleTimeString(),
      });
      /* Dispatch UI orchestration from this response */
      handleAIResponse(res as Parameters<typeof handleAIResponse>[0]);
    } catch (err) {
      addMessage({
        role: "assistant",
        content: err instanceof Error ? err.message : "Something went wrong",
        timestamp: new Date().toLocaleTimeString(),
      });
    } finally {
      setLoading(false);
    }
  }

  function handleBookFromMap(doctor: DoctorPin) {
    setPendingBooking(doctor.id, doctor.name);
    setSelectedDoctor(null);
    /* Prime the AI chat to start the booking flow */
    const bookingMsg = `Book an appointment with ${doctor.name}, doctor ID: ${doctor.id}`;
    handleSend(bookingMsg);
    setChatOpen(true);
  }

  const handleSelectPin = useCallback((pin: DoctorPin) => {
    setSelectedDoctor(pin);
  }, []);

  return (
    <div className="flex flex-col" style={{ height: "100vh" }}>
      <TopBar
        title="Nearby Clinics"
        subtitle={mapFilters.specialty ? `Showing: ${mapFilters.specialty}` : "Find healthcare providers near you"}
      />

      {/* Main area below topbar */}
      <div className="flex flex-1 min-h-0">
        {/* Left: results sidebar */}
        <ResultsSidebar
          pins={visiblePins}
          selectedId={selectedDoctor?.id ?? null}
          filters={{ specialty: localSpecialtyFilter || mapFilters.specialty, query: mapFilters.query }}
          onSelectPin={handleSelectPin}
          onSpecialtyFilter={setLocalSpecialtyFilter}
          isOpen={sidebarOpen}
        />

        {/* Center: map */}
        <div className="flex-1 relative min-h-0">
          {/* Map toggle buttons */}
          <div className="absolute top-3 left-3 z-[999] flex gap-2">
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="flex items-center gap-1.5 bg-white border border-slate-200 shadow-sm rounded-xl px-3 py-1.5 text-xs font-medium text-slate-700 hover:border-indigo-300 transition-colors"
            >
              <SlidersHorizontal size={12} />
              {sidebarOpen ? "Hide list" : "Show list"}
            </button>
          </div>

          {/* AI chat toggle */}
          <div className="absolute top-3 right-3 z-[999]">
            <button
              onClick={() => setChatOpen(!chatOpen)}
              className={cn(
                "flex items-center gap-1.5 shadow-sm rounded-xl px-3 py-1.5 text-xs font-medium transition-colors",
                chatOpen
                  ? "bg-indigo-600 text-white border border-indigo-600"
                  : "bg-white border border-slate-200 text-slate-700 hover:border-indigo-300"
              )}
            >
              <Sparkles size={12} />
              AI Assistant
            </button>
          </div>

          {/* The map itself */}
          <MapClient
            pins={visiblePins}
            selectedId={selectedDoctor?.id ?? null}
            onSelectPin={handleSelectPin}
            userLocation={userLocation ?? undefined}
          />

          {/* Doctor detail float card */}
          {selectedDoctor && (
            <DoctorDetailCard
              doctor={selectedDoctor}
              onClose={() => setSelectedDoctor(null)}
              onBook={handleBookFromMap}
            />
          )}
        </div>

        {/* Right: AI chat panel */}
        {chatOpen && (
          <div className="w-80 shrink-0 flex flex-col border-l border-slate-200 bg-white">
            <div className="flex-1 flex flex-col p-3 overflow-hidden">
              <ChatPanel
                title="Map AI Assistant"
                placeholder='Try: "Find the nearest dentist" or "Cardiologists in Tunis"'
                messages={messages}
                isLoading={isLoading}
                isOpen={chatIsOpen}
                onToggle={togglePanel}
                onSend={handleSend}
                onClear={clearMessages}
              />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
