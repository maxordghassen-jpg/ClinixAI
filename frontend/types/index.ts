/* ── Chat ─────────────────────────────────────────────────── */

export interface Message {
  role: "user" | "assistant";
  content: string;
  timestamp: string;
}

export interface ChatRequest {
  message: string;
  session_id?: string;
  patient_id?: string;
  doctor_id?: string;
  appointment_id?: string;
  latitude?: number;
  longitude?: number;
}

export interface ChatResponse {
  response: string;
  memory?: Record<string, unknown>;
  intent?: Record<string, unknown>;
  data?: unknown;
}

/* ── Appointments ─────────────────────────────────────────── */

export type AppointmentStatus = "pending" | "confirmed" | "cancelled" | "rejected";

export interface Appointment {
  id: string;
  doctor_id: string;
  patient_id: string;
  date: string;
  time: string;
  end_time?: string;
  status: AppointmentStatus;
  doctor_name?: string;
  patient_name?: string;
  specialty?: string;
  notes?: string;
  created_at: string;
  updated_at: string;
}

export interface AppointmentCreate {
  doctor_id: string;
  patient_id: string;
  date: string;
  time: string;
  status?: AppointmentStatus;
  doctor_name?: string;
  patient_name?: string;
  specialty?: string;
  notes?: string;
}

export interface AppointmentReschedule {
  date: string;
  time: string;
}

/* ── Availability ─────────────────────────────────────────── */

export interface AvailabilitySlot {
  start: string;
  end: string;
  status: string;
}

export interface Availability {
  id: string;
  doctor_id: string;
  day: string;
  slots: AvailabilitySlot[];
  ranges?: { start: string; end: string }[];
  consultation_duration_minutes?: number;
}

/* ── Doctor ───────────────────────────────────────────────── */

export interface Doctor {
  id: string;
  name: string;
  specialty: string;
  address?: string;
  phone?: string;
  rating?: number;
  review_count?: number;
  next_available?: string;
  photo_url?: string;
  governorate?: string;
  is_open_now?: boolean;
}

/* ── Patient ──────────────────────────────────────────────── */

export interface Patient {
  id: string;
  name: string;
  email?: string;
  phone?: string;
  date_of_birth?: string;
  blood_type?: string;
  allergies?: string[];
}

/* ── Medical Profile ──────────────────────────────────────── */

export type BloodType       = "A+" | "A-" | "B+" | "B-" | "AB+" | "AB-" | "O+" | "O-";
export type SmokingStatus   = "never" | "former" | "current";
export type AlcoholStatus   = "never" | "occasional" | "moderate" | "heavy";

export interface MedicalProfile {
  // Vitals
  weight?: number | null;
  height?: number | null;
  blood_type?: BloodType | null;
  // Personal
  date_of_birth?: string | null;       // YYYY-MM-DD
  address?: string | null;
  city?: string | null;
  // Lifestyle
  smoking_status?: SmokingStatus | null;
  alcohol_consumption?: AlcoholStatus | null;
  // Medical history
  allergies: string[];
  chronic_conditions: string[];
  current_medications: string[];
  past_surgeries: string[];
  family_history: string[];
  // Emergency contact
  emergency_contact_name?: string | null;
  emergency_contact_phone?: string | null;
  emergency_contact_relationship?: string | null;
}

export interface PatientProfileOut {
  patient_id: string;
  name: string;
  email?: string | null;
  phone?: string | null;
  gender?: string | null;
  preferences?: Record<string, unknown> | null;
  medical: MedicalProfile;
  // AI behavioural signals
  recurring_symptoms: string[];
  preferred_specialties: string[];
  preferred_doctors: Array<{ id: string; name: string; specialty?: string; last_seen?: string }>;
  updated_at?: string | null;
}

export interface ProfileUpdateRequest {
  name?: string;
  phone?: string | null;
  gender?: string | null;
  preferences?: Record<string, unknown>;
  medical?: Partial<MedicalProfile>;
}

export interface MedicalPatchRequest {
  weight?: number | null;
  height?: number | null;
  blood_type?: BloodType | null;
  date_of_birth?: string | null;
  address?: string | null;
  city?: string | null;
  smoking_status?: SmokingStatus | null;
  alcohol_consumption?: AlcoholStatus | null;
  allergies?: string[];
  chronic_conditions?: string[];
  current_medications?: string[];
  past_surgeries?: string[];
  family_history?: string[];
  emergency_contact_name?: string | null;
  emergency_contact_phone?: string | null;
  emergency_contact_relationship?: string | null;
}

/* ── Preconsultation ──────────────────────────────────────── */

export type PreconsultationUrgency = "low" | "medium" | "high";

export interface PreconsultationSummary {
  patient_id: string;
  session_id: string;
  appointment_id?: string | null;
  chief_complaint: string;
  duration: string;
  severity: number;
  associated_symptoms: string[];
  urgency: PreconsultationUrgency;
  summary_text: string;
  created_at: string;
  updated_at?: string | null;
}

/* ── Pre-Consultation Report ──────────────────────────────── */

export interface PatientSnapshot {
  name?: string | null;
  gender?: string | null;
  date_of_birth?: string | null;
  phone?: string | null;
  weight?: number | null;
  height?: number | null;
  blood_type?: string | null;
  smoking_status?: string | null;
  alcohol_consumption?: string | null;
  allergies: string[];
  chronic_conditions: string[];
  current_medications: string[];
  past_surgeries: string[];
  family_history: string[];
  emergency_contact_name?: string | null;
  emergency_contact_phone?: string | null;
  emergency_contact_relationship?: string | null;
}

export interface PreconsultationSnapshot {
  chief_complaint?: string | null;
  duration?: string | null;
  severity?: number | null;
  associated_symptoms: string[];
  urgency?: "low" | "medium" | "high" | null;
}

export interface PreConsultationReport {
  appointment_id: string;
  doctor_id: string;
  patient_id: string;
  patient_snapshot: PatientSnapshot;
  preconsultation_snapshot: PreconsultationSnapshot;
  ai_summary: string;
  created_at: string;
  generated_by: string;
}

/* ── Chat History ─────────────────────────────────────────── */

export interface ChatHistorySummary {
  session_id:  string;
  title:       string;
  language:    string;
  created_at:  string;
  updated_at:  string;
}

export interface ChatHistoryFull extends ChatHistorySummary {
  user_id:   string;
  user_role: "patient" | "doctor";
  messages:  Message[];
}

export interface SaveChatHistoryRequest {
  user_id:   string;
  user_role: "patient" | "doctor";
  session_id: string;
  messages:  Message[];
  language:  string;
}

/* ── Stats ────────────────────────────────────────────────── */

export interface DashboardStats {
  label: string;
  value: number | string;
  change?: string;
  trend?: "up" | "down" | "neutral";
  color: "indigo" | "teal" | "rose" | "amber";
}
