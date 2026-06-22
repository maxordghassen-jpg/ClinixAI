"use client";

import { useState, useEffect, useCallback } from "react";
import { useOrchestrationStore } from "@/stores/useOrchestrationStore";

export type GeoStatus = "idle" | "requesting" | "granted" | "denied" | "unavailable";

export function useGeolocation() {
  const setUserLocation = useOrchestrationStore((s) => s.setUserLocation);
  const storedLocation  = useOrchestrationStore((s) => s.userLocation);

  // Initialise as "granted" when a previous page already resolved the position.
  const [status, setStatus] = useState<GeoStatus>(storedLocation ? "granted" : "idle");

  const request = useCallback(() => {
    if (typeof window === "undefined" || !navigator?.geolocation) {
      setStatus("unavailable");
      return;
    }
    setStatus("requesting");
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setStatus("granted");
        setUserLocation({ lat: pos.coords.latitude, lng: pos.coords.longitude });
      },
      (err) => {
        // code 1 = PERMISSION_DENIED, anything else = technical failure
        setStatus(err.code === 1 ? "denied" : "unavailable");
      },
      { enableHighAccuracy: true, timeout: 10_000, maximumAge: 300_000 },
    );
  }, [setUserLocation]);

  // Auto-request once on mount. Skip if already resolved (e.g. navigated back
  // to a page that calls this hook — the stored value is still valid).
  useEffect(() => {
    if (!storedLocation) request();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return { status, location: storedLocation, request };
}
