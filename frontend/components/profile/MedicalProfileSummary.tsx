"use client";

import { useEffect, useState } from "react";
import {
  Heart, Weight, Ruler, Phone, AlertCircle,
  Loader2, ShieldAlert, Brain, Star, Wine,
} from "lucide-react";
import { getPatientProfileForDoctor } from "@/lib/api";
import { calcAge } from "@/lib/utils";
import PreconsultationSummaryPanel from "@/components/profile/PreconsultationSummary";
import type { PatientProfileOut } from "@/types";

/* ── Helpers ──────────────────────────────────────────────── */

function calcBmi(weight?: number | null, height?: number | null): string | null {
  if (!weight || !height || height === 0) return null;
  return (weight / ((height / 100) ** 2)).toFixed(1);
}

/* ── Sub-components ───────────────────────────────────────── */

type TagColor = "indigo" | "rose" | "amber" | "emerald" | "violet";

function TagList({ items, color = "indigo" }: { items: string[]; color?: TagColor }) {
  if (!items.length) return <span className="text-xs text-slate-400 italic">None recorded</span>;
  const cls: Record<TagColor, string> = {
    indigo:  "bg-indigo-50 text-indigo-700 border-indigo-100",
    rose:    "bg-rose-50 text-rose-700 border-rose-100",
    amber:   "bg-amber-50 text-amber-700 border-amber-100",
    emerald: "bg-emerald-50 text-emerald-700 border-emerald-100",
    violet:  "bg-violet-50 text-violet-700 border-violet-100",
  };
  return (
    <div className="flex flex-wrap gap-1.5 mt-1">
      {items.map((item) => (
        <span key={item} className={`text-xs px-2.5 py-0.5 rounded-full border ${cls[color]}`}>
          {item}
        </span>
      ))}
    </div>
  );
}

function Row({ label, value }: { label: string; value?: string | number | null }) {
  return (
    <div className="flex items-center justify-between py-1.5 border-b border-slate-50 last:border-0">
      <span className="text-xs text-slate-500">{label}</span>
      <span className="text-xs font-medium text-slate-800">{value ?? "—"}</span>
    </div>
  );
}

function SectionCard({
  icon, title, children,
}: {
  icon: React.ReactNode;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="card p-4 space-y-1">
      <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2 flex items-center gap-1.5">
        {icon}
        {title}
      </h4>
      {children}
    </div>
  );
}

/* ── Main component ───────────────────────────────────────── */

interface Props {
  patientId: string;
  patientName?: string;
}

export default function MedicalProfileSummary({ patientId, patientName }: Props) {
  const [profile, setProfile] = useState<PatientProfileOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [denied,  setDenied]  = useState(false);
  const [error,   setError]   = useState<string | null>(null);

  useEffect(() => {
    if (!patientId) return;
    setLoading(true);
    setDenied(false);
    setError(null);

    getPatientProfileForDoctor(patientId)
      .then(setProfile)
      .catch((e: Error) => {
        if (e.message.includes("403")) setDenied(true);
        else setError(e.message);
      })
      .finally(() => setLoading(false));
  }, [patientId]);

  /* ── States ─────────────────────────────────────────────── */

  if (loading) {
    return (
      <div className="flex items-center justify-center py-10">
        <Loader2 size={20} className="animate-spin text-indigo-400" />
      </div>
    );
  }

  if (denied) {
    return (
      <div className="flex flex-col items-center justify-center py-10 gap-3 text-center">
        <div className="w-12 h-12 rounded-2xl bg-amber-50 flex items-center justify-center border border-amber-100">
          <ShieldAlert size={20} className="text-amber-500" />
        </div>
        <div>
          <p className="text-sm font-semibold text-slate-700">Access Restricted</p>
          <p className="text-xs text-slate-400 mt-1 max-w-xs">
            Medical profiles are only visible for patients with a confirmed appointment.
          </p>
        </div>
      </div>
    );
  }

  if (error || !profile) {
    return (
      <div className="text-center py-8 text-xs text-slate-400">
        {error ?? "Profile unavailable"}
      </div>
    );
  }

  const { medical: m } = profile;
  const age = calcAge(m.date_of_birth);
  const bmi = calcBmi(m.weight, m.height);

  const smokingLabel: Record<string, string> = {
    never: "Never smoked",
    former: "Former smoker",
    current: "Current smoker",
  };
  const alcoholLabel: Record<string, string> = {
    never: "Never",
    occasional: "Occasional",
    moderate: "Moderate",
    heavy: "Heavy",
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center gap-2 pb-2 border-b border-slate-100">
        <div className="w-8 h-8 rounded-xl bg-indigo-50 flex items-center justify-center border border-indigo-100">
          <Heart size={14} className="text-indigo-500" />
        </div>
        <div>
          <p className="text-sm font-semibold text-slate-800">
            {patientName ?? profile.name}
          </p>
          <p className="text-xs text-slate-400">Read-only Medical Summary</p>
        </div>
      </div>

      {/* Personal Information */}
      <SectionCard icon={<Ruler size={11} />} title="Personal Information">
        {age !== null && <Row label="Age"    value={`${age} years old`} />}
        {profile.gender   && <Row label="Gender" value={profile.gender} />}
        {profile.phone    && <Row label="Phone"  value={profile.phone} />}
        {m.address        && <Row label="Address" value={m.address} />}
        {age === null && !profile.gender && !profile.phone && !m.address && (
          <span className="text-xs text-slate-400 italic">No personal information recorded</span>
        )}
      </SectionCard>

      {/* Vitals */}
      <SectionCard icon={<Weight size={11} />} title="Vitals">
        <Row label="Weight"     value={m.weight ? `${m.weight} kg` : null} />
        <Row label="Height"     value={m.height ? `${m.height} cm` : null} />
        <Row label="BMI"        value={bmi} />
        <Row label="Blood Type" value={m.blood_type} />
        <Row
          label="Smoking"
          value={m.smoking_status ? smokingLabel[m.smoking_status] : null}
        />
        <Row
          label="Alcohol"
          value={m.alcohol_consumption ? alcoholLabel[m.alcohol_consumption] : null}
        />
      </SectionCard>

      {/* Allergies — highlighted red */}
      <SectionCard
        icon={<AlertCircle size={11} className="text-rose-500" />}
        title="Allergies"
      >
        <TagList items={m.allergies} color="rose" />
      </SectionCard>

      {/* Chronic conditions */}
      <SectionCard icon={<Heart size={11} />} title="Chronic Conditions">
        <TagList items={m.chronic_conditions} color="amber" />
      </SectionCard>

      {/* Medications */}
      <SectionCard icon={<Ruler size={11} />} title="Current Medications">
        <TagList items={m.current_medications} color="indigo" />
      </SectionCard>

      {/* Past surgeries */}
      {m.past_surgeries.length > 0 && (
        <SectionCard icon={<Ruler size={11} />} title="Past Surgeries">
          <TagList items={m.past_surgeries} color="emerald" />
        </SectionCard>
      )}

      {/* Family history */}
      {m.family_history.length > 0 && (
        <SectionCard icon={<Ruler size={11} />} title="Family History">
          <TagList items={m.family_history} color="indigo" />
        </SectionCard>
      )}

      {/* Emergency contact */}
      {(m.emergency_contact_name || m.emergency_contact_phone) && (
        <SectionCard
          icon={<Phone size={11} className="text-emerald-500" />}
          title="Emergency Contact"
        >
          <Row label="Name"         value={m.emergency_contact_name} />
          <Row label="Phone"        value={m.emergency_contact_phone} />
          <Row label="Relationship" value={m.emergency_contact_relationship} />
        </SectionCard>
      )}

      {/* AI Information */}
      {(profile.recurring_symptoms.length > 0 || profile.preferred_specialties.length > 0) && (
        <SectionCard
          icon={<Brain size={11} className="text-violet-500" />}
          title="AI Health Signals"
        >
          {profile.recurring_symptoms.length > 0 && (
            <div className="mb-2">
              <p className="text-xs text-slate-500 mb-1">Recurring Symptoms</p>
              <TagList items={profile.recurring_symptoms} color="rose" />
            </div>
          )}
          {profile.preferred_specialties.length > 0 && (
            <div>
              <p className="text-xs text-slate-500 mb-1">Previous Specialties</p>
              <TagList items={profile.preferred_specialties} color="violet" />
            </div>
          )}
        </SectionCard>
      )}

      {/* Preferred doctors */}
      {profile.preferred_doctors.length > 0 && (
        <SectionCard
          icon={<Star size={11} className="text-amber-500" />}
          title="Previous Doctors"
        >
          <div className="space-y-1">
            {profile.preferred_doctors.slice(0, 3).map((d) => (
              <div key={d.id} className="flex items-center justify-between py-1">
                <span className="text-xs text-slate-700">{d.name}</span>
                {d.specialty && (
                  <span className="text-xs text-slate-400">{d.specialty}</span>
                )}
              </div>
            ))}
          </div>
        </SectionCard>
      )}

      {/* Preconsultation */}
      <PreconsultationSummaryPanel patientId={patientId} />
    </div>
  );
}
