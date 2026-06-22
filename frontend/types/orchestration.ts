/* ── UI action types emitted by the backend AI ───────────────────────────── */

export type UIActionType =
  | "open_map"          // open /patient/map with pins + filters
  | "focus_doctor"      // highlight a specific doctor pin / card
  | "open_booking"      // open booking flow for a known doctor
  | "show_availability"; // show availability panel for a known doctor

/* ── A single pin on the map ─────────────────────────────────────────────── */

export interface DoctorPin {
  id: string;
  name: string;
  specialty?: string;
  address?: string;
  lat: number;
  lng: number;
  phone?: string;
  rating?: number;
  is_open_now?: boolean;
}

/* ── Active map search context ───────────────────────────────────────────── */

export interface MapFilters {
  specialty?: string;
  query?: string;
  placeType?: string;
  governorate?: string;
}

/* ── Payload that accompanies a UIAction ─────────────────────────────────── */

export interface UIActionPayload {
  specialty?: string;
  query?: string;
  place_type?: string;
  pins?: Array<{
    id?: string;
    name?: string;
    address?: string;
    specialty?: string;
    lat?: number | null;
    lng?: number | null;
    phone?: string;
    rating?: number;
    is_open_now?: boolean;
  }>;
  doctor_id?: string;
  doctor_name?: string;
}
