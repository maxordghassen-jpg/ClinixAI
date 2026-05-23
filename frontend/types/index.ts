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
}

export interface ChatResponse {
  response: string;
  memory?: Record<string, unknown>;
  intent?: Record<string, unknown>;
  data?: unknown;
}

export interface AppointmentCreate {
  doctor_id: string;
  patient_id: string;
  date: string;       // YYYY-MM-DD
  time: string;       // HH:MM
}

export interface AppointmentReschedule {
  date: string;
  time: string;
}

export interface Appointment {
  id: string;
  doctor_id: string;
  patient_id: string;
  date: string;
  time: string;
  status: string;
  created_at: string;
  updated_at: string;
}

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
}
