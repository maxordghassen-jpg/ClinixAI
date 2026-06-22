import type { Appointment } from "@/types";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(path, { cache: "no-store" });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

export const getDoctorTodayAppointments = (doctorId: string) =>
  get<Appointment[]>(`/api/appointments/doctor/today/${doctorId}`);

export const getDoctorWeekAppointments = (doctorId: string) =>
  get<Appointment[]>(`/api/appointments/doctor/week/${doctorId}`);

export const getPatientWeekAppointments = (patientId: string) =>
  get<Appointment[]>(`/api/appointments/patient/week/${patientId}`);

export const confirmAppointment = (id: string) =>
  post<Appointment>(`/api/appointments/${id}/confirm`, {});

export const cancelAppointment = (id: string) =>
  post<Appointment>(`/api/appointments/${id}/cancel`, {});
