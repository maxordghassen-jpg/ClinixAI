"use client";

import { useState, useEffect } from "react";
import { Search, SlidersHorizontal, Loader2 } from "lucide-react";
import TopBar from "@/components/layout/TopBar";
import DoctorCard from "@/components/doctors/DoctorCard";
import ChatPanel from "@/components/chat/ChatPanel";
import { usePatientChatStore } from "@/stores/patient/useChatStore";
import { useOrchestrationStore } from "@/stores/useOrchestrationStore";
import { useAIOrchestration } from "@/hooks/useAIOrchestration";
import { useGeolocation } from "@/hooks/useGeolocation";
import { useIdentity } from "@/hooks/useIdentity";
import { patientChat, searchDoctors } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { Doctor } from "@/types";

/* ── Filter options (medical_data_tunisia.doctors taxonomy) ── */
const SPECIALTIES = [
  "All", "Allergologue", "Anesthésiste", "Cardiologue", "Chirurgien", "Dentiste",
  "Dermatologue", "Endocrinologue", "Gastro-entérologue", "Gynécologue",
  "Généraliste", "Gériatre", "Hématologue", "Néphrologue", "ORL", "Oncologue",
  "Ophtalmologue", "Orthopédiste", "Pneumologue", "Psychiatre", "Pédiatre",
  "Radiologue", "Rhumatologue", "Urologue",
];

const GOVERNORATES = [
  "All", "Ariana", "Ben Arous", "Béja", "Bizerte", "Gabès", "Gafsa", "Jendouba",
  "Kairouan", "Kasserine", "Kebili", "Le Kef", "Mahdia", "Manouba", "Medenine",
  "Monastir", "Nabeul", "Sfax", "Sidi Bouzid", "Siliana", "Sousse", "Tataouine",
  "Tozeur", "Tunis", "Zaghouan",
];

/* Debounce delay before firing a search while the user is typing. */
const SEARCH_DEBOUNCE_MS = 350;

export default function PatientDoctorsPage() {
  const [query, setQuery]           = useState("");
  const [specialty, setSpecialty]   = useState("All");
  const [governorate, setGov]       = useState("All");
  const [showFilters, setShowFilters] = useState(false);

  const { patientId, sessionId } = useIdentity();
  const { messages, isLoading, isOpen, addMessage, setLoading, togglePanel, clearMessages } = usePatientChatStore();
  const { handleAIResponse } = useAIOrchestration();
  const { userLocation } = useOrchestrationStore();
  useGeolocation();

  const [doctors, setDoctors] = useState<Doctor[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);

  useEffect(() => {
    const trimmed = query.trim();
    const hasCriteria = trimmed !== "" || specialty !== "All" || governorate !== "All";

    if (!hasCriteria) {
      setDoctors([]);
      setHasSearched(false);
      setSearchLoading(false);
      return;
    }

    let cancelled = false;
    setSearchLoading(true);

    const timer = setTimeout(async () => {
      try {
        const results = await searchDoctors({
          query: trimmed || undefined,
          specialty: specialty !== "All" ? specialty : undefined,
          governorate: governorate !== "All" ? governorate : undefined,
        });
        if (!cancelled) setDoctors(results);
      } catch {
        if (!cancelled) setDoctors([]);
      } finally {
        if (!cancelled) {
          setSearchLoading(false);
          setHasSearched(true);
        }
      }
    }, SEARCH_DEBOUNCE_MS);

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [query, specialty, governorate]);

  async function handleSend(text: string) {
    const ts = new Date().toLocaleTimeString();
    addMessage({ role: "user", content: text, timestamp: ts });
    setLoading(true);
    try {
      const res = await patientChat({ message: text, session_id: sessionId || undefined, patient_id: patientId || undefined, latitude: userLocation?.lat, longitude: userLocation?.lng });
      addMessage({ role: "assistant", content: res.response ?? "(no response)", timestamp: new Date().toLocaleTimeString() });
      handleAIResponse(res as Parameters<typeof handleAIResponse>[0]);
    } catch (err) {
      addMessage({ role: "assistant", content: err instanceof Error ? err.message : "Something went wrong", timestamp: new Date().toLocaleTimeString() });
    } finally {
      setLoading(false);
    }
  }

  function handleBook(doctor: Doctor) {
    togglePanel();
    addMessage({
      role: "user",
      content: `I'd like to book an appointment with ${doctor.name} (${doctor.specialty})`,
      timestamp: new Date().toLocaleTimeString(),
    });
    handleSend(`Book an appointment with ${doctor.name}, doctor ID: ${doctor.id}`);
  }

  return (
    <div className="flex flex-col min-h-full">
      <TopBar title="Find a Doctor" subtitle="Search specialists near you" />

      <div className="flex-1 p-6 gap-6 flex flex-col xl:flex-row">
        {/* Left: search + results */}
        <div className="flex-1 min-w-0 space-y-5">
          {/* Search bar */}
          <div className="flex gap-2">
            <div className="relative flex-1">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search by name or specialty…"
                className="w-full pl-9 pr-4 py-2.5 text-sm bg-white border border-slate-200 rounded-xl focus:outline-none focus:border-indigo-300 focus:ring-2 focus:ring-indigo-100"
              />
            </div>
            <button
              onClick={() => setShowFilters(!showFilters)}
              className={cn(
                "flex items-center gap-1.5 px-3 py-2 rounded-xl text-sm font-medium border transition-colors",
                showFilters
                  ? "bg-indigo-600 text-white border-indigo-600"
                  : "bg-white border-slate-200 text-slate-600 hover:border-indigo-300"
              )}
            >
              <SlidersHorizontal size={14} />
              Filters
            </button>
          </div>

          {/* Filter chips */}
          {showFilters && (
            <div className="card p-4 space-y-4">
              <div>
                <p className="text-xs font-semibold text-slate-500 mb-2 uppercase tracking-wide">Specialty</p>
                <div className="flex flex-wrap gap-2">
                  {SPECIALTIES.map((s) => (
                    <button
                      key={s}
                      onClick={() => setSpecialty(s)}
                      className={cn(
                        "text-xs px-3 py-1.5 rounded-full border font-medium transition-colors",
                        specialty === s
                          ? "bg-indigo-600 text-white border-indigo-600"
                          : "bg-white border-slate-200 text-slate-600 hover:border-indigo-300"
                      )}
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <p className="text-xs font-semibold text-slate-500 mb-2 uppercase tracking-wide">Governorate</p>
                <div className="flex flex-wrap gap-2">
                  {GOVERNORATES.map((g) => (
                    <button
                      key={g}
                      onClick={() => setGov(g)}
                      className={cn(
                        "text-xs px-3 py-1.5 rounded-full border font-medium transition-colors",
                        governorate === g
                          ? "bg-indigo-600 text-white border-indigo-600"
                          : "bg-white border-slate-200 text-slate-600 hover:border-indigo-300"
                      )}
                    >
                      {g}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Count */}
          {hasSearched && !searchLoading && (
            <p className="text-xs text-slate-500">
              {doctors.length} doctor{doctors.length !== 1 ? "s" : ""} found
            </p>
          )}

          {/* Results grid */}
          {searchLoading ? (
            <div className="card p-10 flex flex-col items-center justify-center text-center gap-3">
              <Loader2 size={18} className="text-indigo-400 animate-spin" />
              <p className="text-sm text-slate-500">Searching doctors…</p>
            </div>
          ) : !hasSearched ? (
            <div className="card p-10 flex flex-col items-center justify-center text-center gap-3">
              <p className="text-sm font-medium text-slate-600">Search for a doctor</p>
              <p className="text-xs text-slate-400">Enter a name or specialty, or pick a filter, to get started</p>
            </div>
          ) : doctors.length === 0 ? (
            <div className="card p-10 flex flex-col items-center justify-center text-center gap-3">
              <p className="text-sm font-medium text-slate-600">No doctors found</p>
              <p className="text-xs text-slate-400">Try adjusting your filters or search term</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {doctors.map((doc) => (
                <DoctorCard key={doc.id} doctor={doc} onBook={handleBook} />
              ))}
            </div>
          )}
        </div>

        {/* Right: AI chat */}
        <div className="xl:w-80 shrink-0">
          <ChatPanel
            title="Booking Assistant"
            placeholder="Find a cardiologist, book for tomorrow…"
            messages={messages}
            isLoading={isLoading}
            isOpen={isOpen}
            onToggle={togglePanel}
            onSend={handleSend}
            onClear={clearMessages}
          />
        </div>
      </div>
    </div>
  );
}
