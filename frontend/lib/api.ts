import type {
  Appointment,
  AppointmentCreate,
  AppointmentReschedule,
  Availability,
  AvailabilitySlot,
  ChatHistoryFull,
  ChatHistorySummary,
  ChatRequest,
  ChatResponse,
  Doctor,
  MedicalPatchRequest,
  PatientProfileOut,
  PreconsultationSummary,
  ProfileUpdateRequest,
  SaveChatHistoryRequest,
} from "@/types";

export interface LoginRequest  { email: string; password: string }
export interface SignupRequest { email: string; password: string; name: string }
export interface TokenResponse {
  access_token: string;
  token_type: string;
  role: "patient" | "doctor";
  name: string;
  patient_profile_id: string | null;
  doctor_id: string | null;
}

// ── Auth token helper ─────────────────────────────────────────────────────────
// Reads the persisted Zustand auth store directly from localStorage so this
// module can include the Bearer header without being a React component.

function getToken(): string {
  if (typeof window === "undefined") return "";
  try {
    const raw = localStorage.getItem("clinix-auth");
    return JSON.parse(raw ?? "{}")?.state?.token ?? "";
  } catch {
    return "";
  }
}

// ── Core fetch helper ─────────────────────────────────────────────────────────

async function request<T>(
  path: string,
  { headers, ...rest }: RequestInit = {}
): Promise<T> {
  const res = await fetch(path, {
    ...rest,
    headers: {
      "Content-Type": "application/json",
      ...(headers as Record<string, string>),
    },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText}: ${text}`);
  }
  // 204/205 have no body — return undefined instead of calling res.json() which
  // would throw SyntaxError("Unexpected end of JSON input") on an empty response
  if (res.status === 204 || res.status === 205) return undefined as T;
  return res.json() as Promise<T>;
}

// ── Auth ──────────────────────────────────────────────────────────────────────

export const authLogin = (body: LoginRequest) =>
  request<TokenResponse>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify(body),
  });

export const authSignup = (body: SignupRequest) =>
  request<TokenResponse>("/api/auth/signup", {
    method: "POST",
    body: JSON.stringify(body),
  });

export const authMe = (token: string) =>
  request<TokenResponse>("/api/auth/me", {
    headers: { Authorization: `Bearer ${token}` } as Record<string, string>,
  });

// ── Chat ──────────────────────────────────────────────────────────────────────
// JWT is automatically included so the agent service can derive identity
// from the token rather than relying solely on the request body.

export const patientChat = (body: ChatRequest) =>
  request<ChatResponse>("/api/patient/chat", {
    method: "POST",
    body: JSON.stringify(body),
    headers: { Authorization: `Bearer ${getToken()}` },
  });

export const doctorChat = (body: ChatRequest) =>
  request<ChatResponse>("/api/doctor/chat", {
    method: "POST",
    body: JSON.stringify(body),
    headers: { Authorization: `Bearer ${getToken()}` },
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

// ── Longitudinal memory ───────────────────────────────────────────────────────

export const getUserMemory = (userId: string, query?: string) => {
  const path = query
    ? `/api/memory/${userId}?q=${encodeURIComponent(query)}`
    : `/api/memory/${userId}`;
  return request<import("@/services/api/memory").UserMemoryResponse>(path, {
    headers: { Authorization: `Bearer ${getToken()}` },
  });
};

// ── Medical Profile (patient) ─────────────────────────────────────────────────

export const getMyProfile = () =>
  request<PatientProfileOut>("/api/profile", {
    headers: { Authorization: `Bearer ${getToken()}` },
  });

export const updateMyProfile = (body: ProfileUpdateRequest) =>
  request<PatientProfileOut>("/api/profile", {
    method: "PUT",
    body: JSON.stringify(body),
    headers: { Authorization: `Bearer ${getToken()}` },
  });

export const patchMyMedical = (body: MedicalPatchRequest) =>
  request<PatientProfileOut>("/api/profile/medical", {
    method: "PATCH",
    body: JSON.stringify(body),
    headers: { Authorization: `Bearer ${getToken()}` },
  });

// ── Medical Profile (doctor) ──────────────────────────────────────────────────

export const getPatientProfileForDoctor = (patientId: string) =>
  request<PatientProfileOut>(`/api/profile/doctor/${patientId}`, {
    headers: { Authorization: `Bearer ${getToken()}` },
  });

// ── Preconsultation ───────────────────────────────────────────────────────────

export const getPreconsultationSummary = (patientId: string) =>
  request<PreconsultationSummary>(`/api/preconsultation/${patientId}`, {
    headers: { Authorization: `Bearer ${getToken()}` },
  });

// ── Pre-Consultation Reports (doctor) ─────────────────────────────────────────

export const getAppointmentReport = (appointmentId: string) =>
  request<import("@/types").PreConsultationReport>(
    `/api/report/${appointmentId}`,
    { headers: { Authorization: `Bearer ${getToken()}` } },
  );

// ── Chat History ──────────────────────────────────────────────────────────────

export const saveChatHistory = (body: SaveChatHistoryRequest) =>
  request<void>("/api/chat/history/save", {
    method: "POST",
    body: JSON.stringify(body),
    headers: { Authorization: `Bearer ${getToken()}` },
  });

export const listChatHistory = (userRole: string, userId: string) =>
  request<ChatHistorySummary[]>(`/api/chat/history/${userRole}/${userId}`, {
    headers: { Authorization: `Bearer ${getToken()}` },
  });

export const getChatHistorySession = (
  userRole: string,
  userId: string,
  sessionId: string,
) =>
  request<ChatHistoryFull>(
    `/api/chat/history/${userRole}/${userId}/${sessionId}`,
    { headers: { Authorization: `Bearer ${getToken()}` } },
  );

export const deleteChatHistorySession = (
  userRole: string,
  userId: string,
  sessionId: string,
) =>
  request<void>(`/api/chat/history/${userRole}/${userId}/${sessionId}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${getToken()}` },
  });

export const deleteAllChatHistory = (userRole: string, userId: string) =>
  request<void>(`/api/chat/history/${userRole}/${userId}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${getToken()}` },
  });

// ── Doctor Search (Find Doctors page) ───────────────────────────────────────────
// Proxies to geo_service /api/search/manual (medical_data_tunisia.doctors).

interface GeoDoctorResult {
  id: string;
  name: string;
  address?: string | null;
  phone_number?: string | null;
  rating?: number | null;
  user_ratings_total?: number | null;
  is_open_now?: boolean | null;
  specialty?: string | null;
  governorate?: string | null;
  image_url?: string | null;
}

interface GeoSearchResponse {
  success: boolean;
  results: GeoDoctorResult[];
  results_count: number;
}

export interface DoctorSearchParams {
  query?: string;
  specialty?: string;
  governorate?: string;
  limit?: number;
}

export async function searchDoctors(params: DoctorSearchParams): Promise<Doctor[]> {
  const { query, specialty, governorate, limit } = params;

  // geo_service requires at least one search criterion.
  if (!query && !specialty && !governorate) return [];

  const data = await request<GeoSearchResponse>("/api/geo/search", {
    method: "POST",
    body: JSON.stringify({
      category: "doctors",
      ...(query ? { query } : {}),
      ...(specialty ? { specialty } : {}),
      ...(governorate ? { governorate } : {}),
      ...(limit ? { limit } : {}),
    }),
  });

  return (data.results ?? []).map((d): Doctor => ({
    id: d.id,
    name: d.name,
    specialty: d.specialty ?? "",
    address: d.address ?? undefined,
    phone: d.phone_number ?? undefined,
    rating: d.rating ?? undefined,
    review_count: d.user_ratings_total ?? undefined,
    photo_url: d.image_url ?? undefined,
    governorate: d.governorate ?? undefined,
    is_open_now: d.is_open_now ?? undefined,
  }));
}
