"use client";

import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import type { UIActionType, UIActionPayload, DoctorPin, MapFilters } from "@/types/orchestration";

export interface UserLocation {
  lat: number;
  lng: number;
}

interface OrchestrationState {
  /* Current pending UI action from the AI */
  uiAction: UIActionType | null;
  uiPayload: UIActionPayload | null;

  /* Map state */
  mapPins: DoctorPin[];
  mapFilters: MapFilters;
  selectedDoctor: DoctorPin | null;

  /* Booking intent from map interaction */
  pendingBookingDoctorId: string | null;
  pendingBookingDoctorName: string | null;

  /* User's real-world coordinates (set once location permission is granted) */
  userLocation: UserLocation | null;

  /* Actions */
  dispatch: (action: UIActionType, payload?: UIActionPayload) => void;
  clearAction: () => void;
  setMapPins: (pins: DoctorPin[]) => void;
  setMapFilters: (filters: MapFilters) => void;
  selectDoctor: (doctor: DoctorPin | null) => void;
  setPendingBooking: (doctorId: string | null, doctorName?: string) => void;
  clearMap: () => void;
  setUserLocation: (loc: UserLocation | null) => void;
}

export const useOrchestrationStore = create<OrchestrationState>()(
  persist(
    (set) => ({
      uiAction:                null,
      uiPayload:               null,
      mapPins:                 [],
      mapFilters:              {},
      selectedDoctor:          null,
      pendingBookingDoctorId:  null,
      pendingBookingDoctorName: null,
      userLocation:            null,

      dispatch: (action, payload) =>
        set({ uiAction: action, uiPayload: payload ?? null }),

      clearAction: () =>
        set({ uiAction: null, uiPayload: null }),

      setMapPins: (pins) =>
        set({ mapPins: pins }),

      setMapFilters: (filters) =>
        set((s) => ({ mapFilters: { ...s.mapFilters, ...filters } })),

      selectDoctor: (doctor) =>
        set({ selectedDoctor: doctor }),

      setPendingBooking: (doctorId, doctorName) =>
        set({ pendingBookingDoctorId: doctorId, pendingBookingDoctorName: doctorName ?? null }),

      clearMap: () =>
        set({ mapPins: [], mapFilters: {}, selectedDoctor: null }),

      setUserLocation: (loc) =>
        set({ userLocation: loc }),
    }),
    {
      name: "clinix-map-state",
      storage: createJSONStorage(() =>
        typeof window !== "undefined"
          ? sessionStorage
          : {
              getItem:    () => null,
              setItem:    () => {},
              removeItem: () => {},
            }
      ),
      /* Only persist map-related state — userLocation is re-acquired per session */
      partialize: (state) => ({
        mapPins:    state.mapPins,
        mapFilters: state.mapFilters,
      }),
    }
  )
);
