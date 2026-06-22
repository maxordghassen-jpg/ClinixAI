"use client";

import { useRouter } from "next/navigation";
import { useOrchestrationStore } from "@/stores/useOrchestrationStore";
import type { UIActionPayload, DoctorPin } from "@/types/orchestration";

/* Tunisia-centered fallback coordinates for demo / offline mode.
   When geo_service returns places without lat/lng, we scatter pins
   around Tunis so the map is still populated visually. */
const TUNIS_CENTER = { lat: 36.8065, lng: 10.1815 };

function normalizePins(
  rawPins: UIActionPayload["pins"],
  specialty?: string
): DoctorPin[] {
  if (!rawPins?.length) return [];

  return rawPins.map((p, i) => {
    /* Force numeric coercion — backend may occasionally return stringified floats */
    const rawLat = Number(p.lat);
    const rawLng = Number(p.lng);

    const lat =
      Number.isFinite(rawLat) && rawLat !== 0
        ? rawLat
        : TUNIS_CENTER.lat + (i - 2) * 0.012;
    const lng =
      Number.isFinite(rawLng) && rawLng !== 0
        ? rawLng
        : TUNIS_CENTER.lng + (i - 2) * 0.015;

    return {
      id:          p.id       ?? `pin-${i}`,
      name:        p.name     ?? "Unknown",
      specialty:   p.specialty ?? specialty,
      address:     p.address,
      phone:       p.phone,
      rating:      p.rating,
      is_open_now: p.is_open_now,
      lat,
      lng,
    };
  });
}

export interface AIResponse {
  response?: string;
  ui_action?: string;
  ui_payload?: UIActionPayload;
  memory?: Record<string, unknown>;
}

export function useAIOrchestration() {
  const router = useRouter();
  const { dispatch, setMapPins, setMapFilters, clearAction } = useOrchestrationStore();

  function handleAIResponse(res: AIResponse) {
    const action  = res.ui_action;
    const payload = res.ui_payload;

    if (!action) return;

    switch (action) {
      case "open_map": {
        console.log("[MAP FLOW] incoming ui_payload", payload);

        const pins = normalizePins(payload?.pins, payload?.specialty);
        console.log("[MAP FLOW] stored pins", pins.length, pins);

        /* Persist pins and filters to Zustand BEFORE navigation.
           Zustand's set() is synchronous so the store is updated before
           router.push() fires, but we defer navigation one microtask to
           guarantee React has committed the update. */
        setMapPins(pins);
        setMapFilters({
          specialty: payload?.specialty,
          query:     payload?.query,
          placeType: payload?.place_type,
        });
        dispatch("open_map", payload);

        /* Defer navigation by one microtask so Zustand's sessionStorage
           persist middleware has time to flush before the new page mounts. */
        Promise.resolve().then(() => router.push("/patient/map"));
        break;
      }

      case "focus_doctor": {
        dispatch("focus_doctor", payload);
        break;
      }

      case "open_booking": {
        dispatch("open_booking", payload);
        break;
      }

      case "show_availability": {
        dispatch("show_availability", payload);
        break;
      }

      default:
        break;
    }
  }

  return { handleAIResponse, clearAction };
}
