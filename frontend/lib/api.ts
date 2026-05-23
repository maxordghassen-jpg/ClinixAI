import type {
  Appointment,
  AppointmentCreate,
  AppointmentReschedule,
  Availability,
  AvailabilitySlot,
  ChatRequest,
  ChatResponse,
} from "@/types";

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText}: ${text}`);
  }
  return res.json() as Promise<T>;
}

// ── Chat ──────────────────────────────────────────────────────────────────────

export const patientChat = (body: ChatRequest) =>
  request<ChatResponse>("/api/patient/chat", {
    method: "POST",
    body: JSON.stringify(body),
  });

export const doctorChat = (body: ChatRequest) =>
  request<ChatResponse>("/api/doctor/chat", {
    method: "POST",
    body: JSON.stringify(body),
  });

// ── Appointments ──────────────────────────────────────────────────────────────

export const createAppointment = (body: AppointmentCreate) =>
  request<Appointment>("/api/appointments", {
    method: "POST",
    body: JSON.stringify(body),
  });

export const cancelAppointment = (id: string) =>
  request<Appointment>(`/api/appointments/${id}/cancel`, { method: "POST" });

export const rescheduleAppointment = (id: string, body: AppointmentReschedule) =>
  request<Appointment>(`/api/appointments/${id}/reschedule`, {
    method: "POST",
    body: JSON.stringify(body),
  });

export const getPatientAppointmentsWeek = (patientId: string) =>
  request<Appointment[]>(`/api/appointments/patient/week/${patientId}`);

// ── Availability ──────────────────────────────────────────────────────────────

export const getDoctorAvailability = (doctorId: string) =>
  request<Availability[]>(`/api/availability/${doctorId}`);

export const createAvailability = (body: {
  doctor_id: string;
  day: string;
  slots: { start: string; end: string }[];
}) =>
  request<Availability>("/api/availability", {
    method: "POST",
    body: JSON.stringify(body),
  });

export const getFreeSlots = (doctorId: string, date: string) =>
  request<AvailabilitySlot[]>(`/api/availability/${doctorId}/${date}/free-slots`);
