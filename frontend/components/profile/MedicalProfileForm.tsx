"use client";

import { useEffect, useState } from "react";
import {
  Heart, Weight, Ruler, Cigarette, Wine, Phone,
  MapPin, Calendar, Plus, X, Save, Loader2,
  AlertCircle, AlertTriangle, RefreshCcw, User,
} from "lucide-react";
import { getMyProfile, patchMyMedical, updateMyProfile } from "@/lib/api";
import type {
  AlcoholStatus, BloodType, MedicalPatchRequest, MedicalProfile,
  PatientProfileOut, SmokingStatus,
} from "@/types";

/* ── Constants ────────────────────────────────────────────── */

const BLOOD_TYPES: BloodType[] = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"];

const SMOKING_OPTIONS: { value: SmokingStatus; label: string }[] = [
  { value: "never",   label: "Never" },
  { value: "former",  label: "Former smoker" },
  { value: "current", label: "Current smoker" },
];

const ALCOHOL_OPTIONS: { value: AlcoholStatus; label: string }[] = [
  { value: "never",      label: "Never" },
  { value: "occasional", label: "Occasional" },
  { value: "moderate",   label: "Moderate" },
  { value: "heavy",      label: "Heavy" },
];

const GENDER_OPTIONS = [
  { value: "male",   label: "Male" },
  { value: "female", label: "Female" },
  { value: "other",  label: "Other" },
];

/* ── Sub-components ───────────────────────────────────────── */

function SectionCard({
  icon, title, color = "indigo", children,
}: {
  icon: React.ReactNode;
  title: string;
  color?: "indigo" | "rose" | "amber" | "emerald" | "violet";
  children: React.ReactNode;
}) {
  const border: Record<string, string> = {
    indigo: "border-indigo-100",
    rose:   "border-rose-100",
    amber:  "border-amber-100",
    emerald:"border-emerald-100",
    violet: "border-violet-100",
  };
  return (
    <div className={`card p-5 space-y-4 border ${border[color]}`}>
      <h3 className="text-sm font-semibold text-slate-700 flex items-center gap-2">
        {icon}
        {title}
      </h3>
      {children}
    </div>
  );
}

function FieldRow({ children }: { children: React.ReactNode }) {
  return <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">{children}</div>;
}

function Field({
  label, icon, children,
}: {
  label: string;
  icon?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label className="block text-xs font-medium text-slate-600 mb-1.5 flex items-center gap-1">
        {icon}
        {label}
      </label>
      {children}
    </div>
  );
}

const inputCls =
  "w-full text-sm px-3 py-1.5 rounded-lg border border-slate-200 " +
  "focus:border-indigo-400 focus:ring-1 focus:ring-indigo-200 outline-none transition-all";

const readOnlyCls =
  "w-full text-sm px-3 py-1.5 rounded-lg border border-slate-100 bg-slate-50 text-slate-500";

function PillSelect<T extends string>({
  options,
  value,
  onChange,
}: {
  options: { value: T; label: string }[];
  value: T | null | undefined;
  onChange: (v: T | null) => void;
}) {
  return (
    <div className="flex gap-2 flex-wrap">
      {options.map((opt) => (
        <button
          key={opt.value}
          type="button"
          onClick={() => onChange(value === opt.value ? null : opt.value)}
          className={`text-xs px-3 py-1.5 rounded-full border transition-all ${
            value === opt.value
              ? "bg-indigo-600 text-white border-indigo-600"
              : "bg-white text-slate-600 border-slate-200 hover:border-indigo-300"
          }`}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}

function TagInput({
  label,
  values,
  onChange,
  placeholder,
}: {
  label: string;
  values: string[];
  onChange: (v: string[]) => void;
  placeholder: string;
}) {
  const [input, setInput] = useState("");

  function add() {
    const trimmed = input.trim();
    if (trimmed && !values.includes(trimmed)) {
      onChange([...values, trimmed]);
    }
    setInput("");
  }

  return (
    <div>
      <label className="block text-xs font-medium text-slate-600 mb-1.5">{label}</label>
      <div className="flex flex-wrap gap-1.5 mb-2 min-h-[28px]">
        {values.map((v) => (
          <span
            key={v}
            className="inline-flex items-center gap-1 text-xs px-2.5 py-1 rounded-full
                       bg-indigo-50 text-indigo-700 border border-indigo-100"
          >
            {v}
            <button
              type="button"
              onClick={() => onChange(values.filter((x) => x !== v))}
              className="hover:text-indigo-900"
            >
              <X size={10} />
            </button>
          </span>
        ))}
      </div>
      <div className="flex gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              add();
            }
          }}
          placeholder={placeholder}
          className={`flex-1 ${inputCls}`}
        />
        <button
          type="button"
          onClick={add}
          className="flex items-center gap-1 text-xs px-2.5 py-1.5 rounded-lg
                     bg-indigo-50 text-indigo-600 hover:bg-indigo-100
                     border border-indigo-200 transition-colors"
        >
          <Plus size={12} /> Add
        </button>
      </div>
    </div>
  );
}

/* ── Helpers ──────────────────────────────────────────────── */

interface PersonalInfo {
  name: string;
  phone: string;
  gender: string;
}

function emptyPersonal(): PersonalInfo {
  return { name: "", phone: "", gender: "" };
}

function emptyForm(): MedicalPatchRequest {
  return {
    weight: null, height: null, blood_type: null,
    date_of_birth: null, address: null, city: null,
    smoking_status: null, alcohol_consumption: null,
    allergies: [], chronic_conditions: [], current_medications: [],
    past_surgeries: [], family_history: [],
    emergency_contact_name: null, emergency_contact_phone: null,
    emergency_contact_relationship: null,
  };
}

function populatePersonal(p: PatientProfileOut): PersonalInfo {
  return {
    name:   p.name   ?? "",
    phone:  p.phone  ?? "",
    gender: p.gender ?? "",
  };
}

function populateForm(m: MedicalProfile): MedicalPatchRequest {
  return {
    weight:                         m.weight                         ?? null,
    height:                         m.height                         ?? null,
    blood_type:                     m.blood_type                     ?? null,
    date_of_birth:                  m.date_of_birth                  ?? null,
    address:                        m.address                        ?? null,
    city:                           m.city                           ?? null,
    smoking_status:                 m.smoking_status                 ?? null,
    alcohol_consumption:            m.alcohol_consumption            ?? null,
    allergies:                      m.allergies                      ?? [],
    chronic_conditions:             m.chronic_conditions             ?? [],
    current_medications:            m.current_medications            ?? [],
    past_surgeries:                 m.past_surgeries                 ?? [],
    family_history:                 m.family_history                 ?? [],
    emergency_contact_name:         m.emergency_contact_name         ?? null,
    emergency_contact_phone:        m.emergency_contact_phone        ?? null,
    emergency_contact_relationship: m.emergency_contact_relationship ?? null,
  };
}

/* ── Main component ───────────────────────────────────────── */

export default function MedicalProfileForm() {
  const [personal, setPersonal] = useState<PersonalInfo>(emptyPersonal());
  const [form,     setForm]     = useState<MedicalPatchRequest>(emptyForm());
  const [loading,  setLoading]  = useState(true);
  const [loadErr,  setLoadErr]  = useState<string | null>(null);
  const [saving,   setSaving]   = useState(false);
  const [saved,    setSaved]    = useState(false);
  const [saveErr,  setSaveErr]  = useState<string | null>(null);

  function loadProfile() {
    setLoading(true);
    setLoadErr(null);
    getMyProfile()
      .then((p) => {
        setPersonal(populatePersonal(p));
        setForm(populateForm(p.medical));
      })
      .catch((e: Error) =>
        setLoadErr(
          e.message.includes("401") || e.message.includes("403")
            ? "Authentication error. Please log out and sign in again."
            : e.message.includes("404")
            ? "Your medical profile has not been created yet. Fill in your details and save to create it."
            : `Failed to load profile: ${e.message}`
        )
      )
      .finally(() => setLoading(false));
  }

  useEffect(() => { loadProfile(); }, []);

  async function handleSave() {
    setSaving(true);
    setSaveErr(null);
    setSaved(false);
    try {
      // Save personal info (phone, gender) via PUT /profile
      // and medical data via PATCH /profile/medical in parallel.
      await Promise.all([
        updateMyProfile({
          phone:  personal.phone  || null,
          gender: personal.gender || null,
        }),
        patchMyMedical(form),
      ]);
      setSaved(true);
      setTimeout(() => setSaved(false), 4000);
    } catch (e) {
      setSaveErr(e instanceof Error ? e.message : "Save failed — please try again.");
    } finally {
      setSaving(false);
    }
  }

  /* ── Loading ───────────────────────────────────────────── */
  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-20 gap-3 text-center">
        <Loader2 size={24} className="animate-spin text-indigo-400" />
        <p className="text-sm text-slate-400">Loading your medical profile…</p>
      </div>
    );
  }

  /* ── Load error ────────────────────────────────────────── */
  if (loadErr && !loadErr.includes("not been created")) {
    return (
      <div className="card p-8 flex flex-col items-center gap-4 text-center border-rose-100">
        <div className="w-12 h-12 rounded-2xl bg-rose-50 flex items-center justify-center border border-rose-100">
          <AlertTriangle size={20} className="text-rose-500" />
        </div>
        <div>
          <p className="text-sm font-semibold text-slate-700">Could not load profile</p>
          <p className="text-xs text-slate-500 mt-1 max-w-xs">{loadErr}</p>
        </div>
        <button
          onClick={loadProfile}
          className="flex items-center gap-2 text-sm px-4 py-2 rounded-lg
                     bg-indigo-50 text-indigo-600 hover:bg-indigo-100
                     border border-indigo-200 transition-colors"
        >
          <RefreshCcw size={13} /> Try again
        </button>
      </div>
    );
  }

  /* ── Form ──────────────────────────────────────────────── */
  return (
    <div className="space-y-5">
      {/* New profile notice */}
      {loadErr?.includes("not been created") && (
        <div className="flex items-start gap-3 p-3 rounded-lg bg-indigo-50 border border-indigo-100">
          <AlertCircle size={14} className="text-indigo-500 mt-0.5 shrink-0" />
          <p className="text-xs text-indigo-700">{loadErr}</p>
        </div>
      )}

      {/* Account Information */}
      <SectionCard
        icon={<User size={14} className="text-indigo-500" />}
        title="Account Information"
        color="indigo"
      >
        <FieldRow>
          <Field label="Full Name">
            <input
              type="text"
              value={personal.name}
              readOnly
              className={readOnlyCls}
              title="Name is set at registration"
            />
          </Field>
          <Field label="Phone Number" icon={<Phone size={12} />}>
            <input
              type="tel"
              value={personal.phone}
              onChange={(e) => setPersonal({ ...personal, phone: e.target.value })}
              placeholder="+216 XX XXX XXX"
              className={inputCls}
            />
          </Field>
        </FieldRow>
        <Field label="Gender">
          <PillSelect
            options={GENDER_OPTIONS}
            value={personal.gender as "male" | "female" | "other" | null}
            onChange={(v) => setPersonal({ ...personal, gender: v ?? "" })}
          />
        </Field>
      </SectionCard>

      {/* Personal Information */}
      <SectionCard
        icon={<Calendar size={14} className="text-violet-500" />}
        title="Personal Information"
        color="violet"
      >
        <FieldRow>
          <Field label="Date of Birth" icon={<Calendar size={12} />}>
            <input
              type="date"
              value={form.date_of_birth ?? ""}
              onChange={(e) =>
                setForm({ ...form, date_of_birth: e.target.value || null })
              }
              className={inputCls}
            />
          </Field>
          <Field label="Address" icon={<MapPin size={12} />}>
            <input
              type="text"
              value={form.address ?? ""}
              onChange={(e) =>
                setForm({ ...form, address: e.target.value || null })
              }
              placeholder="Street address"
              className={inputCls}
            />
          </Field>
        </FieldRow>
        <FieldRow>
          <Field label="City" icon={<MapPin size={12} />}>
            <input
              type="text"
              value={form.city ?? ""}
              onChange={(e) =>
                setForm({ ...form, city: e.target.value || null })
              }
              placeholder="e.g. Tunis"
              className={inputCls}
            />
          </Field>
        </FieldRow>
      </SectionCard>

      {/* Vitals */}
      <SectionCard
        icon={<Heart size={14} className="text-rose-500" />}
        title="Vitals"
        color="rose"
      >
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
          <Field label="Weight (kg)" icon={<Weight size={12} />}>
            <input
              type="number"
              step="0.1"
              min="0"
              value={form.weight ?? ""}
              onChange={(e) =>
                setForm({ ...form, weight: e.target.value ? parseFloat(e.target.value) : null })
              }
              placeholder="70"
              className={inputCls}
            />
          </Field>
          <Field label="Height (cm)" icon={<Ruler size={12} />}>
            <input
              type="number"
              step="0.5"
              min="0"
              value={form.height ?? ""}
              onChange={(e) =>
                setForm({ ...form, height: e.target.value ? parseFloat(e.target.value) : null })
              }
              placeholder="175"
              className={inputCls}
            />
          </Field>
          <Field label="Blood Type">
            <select
              value={form.blood_type ?? ""}
              onChange={(e) =>
                setForm({ ...form, blood_type: (e.target.value as BloodType) || null })
              }
              className={`${inputCls} bg-white`}
            >
              <option value="">Unknown</option>
              {BLOOD_TYPES.map((bt) => (
                <option key={bt} value={bt}>{bt}</option>
              ))}
            </select>
          </Field>
        </div>
      </SectionCard>

      {/* Lifestyle */}
      <SectionCard
        icon={<Cigarette size={14} className="text-amber-500" />}
        title="Lifestyle"
        color="amber"
      >
        <Field label="Smoking Status" icon={<Cigarette size={12} />}>
          <PillSelect
            options={SMOKING_OPTIONS}
            value={form.smoking_status}
            onChange={(v) => setForm({ ...form, smoking_status: v })}
          />
        </Field>
        <Field label="Alcohol Consumption" icon={<Wine size={12} />}>
          <PillSelect
            options={ALCOHOL_OPTIONS}
            value={form.alcohol_consumption}
            onChange={(v) => setForm({ ...form, alcohol_consumption: v })}
          />
        </Field>
      </SectionCard>

      {/* Medical History */}
      <SectionCard
        icon={<AlertCircle size={14} className="text-indigo-500" />}
        title="Medical History"
      >
        <TagInput
          label="Allergies"
          values={form.allergies ?? []}
          onChange={(v) => setForm({ ...form, allergies: v })}
          placeholder="e.g. Penicillin, Pollen"
        />
        <TagInput
          label="Chronic Conditions"
          values={form.chronic_conditions ?? []}
          onChange={(v) => setForm({ ...form, chronic_conditions: v })}
          placeholder="e.g. Diabetes, Hypertension"
        />
        <TagInput
          label="Current Medications"
          values={form.current_medications ?? []}
          onChange={(v) => setForm({ ...form, current_medications: v })}
          placeholder="e.g. Metformin 500mg"
        />
        <TagInput
          label="Past Surgeries"
          values={form.past_surgeries ?? []}
          onChange={(v) => setForm({ ...form, past_surgeries: v })}
          placeholder="e.g. Appendectomy 2018"
        />
        <TagInput
          label="Family History"
          values={form.family_history ?? []}
          onChange={(v) => setForm({ ...form, family_history: v })}
          placeholder="e.g. Heart disease (father)"
        />
      </SectionCard>

      {/* Emergency Contact */}
      <SectionCard
        icon={<Phone size={14} className="text-emerald-500" />}
        title="Emergency Contact"
        color="emerald"
      >
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <Field label="Contact Name">
            <input
              type="text"
              value={form.emergency_contact_name ?? ""}
              onChange={(e) =>
                setForm({ ...form, emergency_contact_name: e.target.value || null })
              }
              placeholder="Full name"
              className={inputCls}
            />
          </Field>
          <Field label="Contact Phone">
            <input
              type="tel"
              value={form.emergency_contact_phone ?? ""}
              onChange={(e) =>
                setForm({ ...form, emergency_contact_phone: e.target.value || null })
              }
              placeholder="+216 XX XXX XXX"
              className={inputCls}
            />
          </Field>
          <Field label="Relationship">
            <input
              type="text"
              value={form.emergency_contact_relationship ?? ""}
              onChange={(e) =>
                setForm({ ...form, emergency_contact_relationship: e.target.value || null })
              }
              placeholder="e.g. Spouse, Parent"
              className={inputCls}
            />
          </Field>
        </div>
      </SectionCard>

      {/* Save bar */}
      <div className="flex items-center gap-3 pt-1">
        <button
          onClick={handleSave}
          disabled={saving}
          className="btn-primary flex items-center gap-2 px-5 py-2.5 text-sm"
        >
          {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
          {saving ? "Saving…" : "Save Profile"}
        </button>
        {saved && (
          <span className="text-sm text-emerald-600 font-medium">
            ✓ Saved successfully
          </span>
        )}
        {saveErr && (
          <span className="text-sm text-rose-600 flex items-center gap-1">
            <AlertCircle size={13} /> {saveErr}
          </span>
        )}
      </div>
    </div>
  );
}
