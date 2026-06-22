"use client";

import "maplibre-gl/dist/maplibre-gl.css";
import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import Map, { Marker, Popup, NavigationControl } from "react-map-gl/maplibre";
import type { MapRef } from "react-map-gl/maplibre";
import { Star, Phone, X } from "lucide-react";
import { cn } from "@/lib/utils";
import type { DoctorPin } from "@/types/orchestration";

const MAP_STYLE =
  process.env.NEXT_PUBLIC_MAP_STYLE_URL ??
  "https://demotiles.maplibre.org/style.json";

/* Default initial center — fits all of Tunisia at zoom 7 so any real
   coordinates will be visible before fitBounds zooms in. */
const INITIAL_VIEW = { longitude: 9.5375, latitude: 33.8869, zoom: 6 } as const;

/* ── Specialty colors ─────────────────────────────────────────────────────── */

const SPECIALTY_COLORS: Record<string, string> = {
  cardiologist:    "#f43f5e",
  cardiologue:     "#f43f5e",
  dermatologist:   "#f59e0b",
  dermatologue:    "#f59e0b",
  neurologist:     "#8b5cf6",
  neurologue:      "#8b5cf6",
  dentist:         "#06b6d4",
  dentiste:        "#06b6d4",
  pediatrician:    "#10b981",
  "pédiatre":      "#10b981",
  ophthalmologist: "#3b82f6",
  ophtalmologue:   "#3b82f6",
  pharmacy:        "#84cc16",
  pharmacie:       "#84cc16",
  clinic:          "#6366f1",
};

function pinColor(specialty?: string): string {
  if (!specialty) return "#6366f1";
  return SPECIALTY_COLORS[specialty.toLowerCase()] ?? "#6366f1";
}

/* ── Pin SVG ─────────────────────────────────────────────────────────────── */

function PinSvg({ specialty, selected }: { specialty?: string; selected: boolean }) {
  const color = pinColor(specialty);
  const size  = selected ? 36 : 28;
  const h     = Math.round(size * 1.4);
  return (
    <svg
      width={size}
      height={h}
      viewBox="0 0 28 40"
      style={{
        filter: selected
          ? `drop-shadow(0 3px 8px ${color}99)`
          : "drop-shadow(0 1px 4px rgba(0,0,0,.4))",
        transition: "all 0.15s ease",
        cursor: "pointer",
        display: "block",
      }}
    >
      <path
        d="M14 0C6.268 0 0 6.268 0 14c0 10.5 14 26 14 26S28 24.5 28 14C28 6.268 21.732 0 14 0z"
        fill={color}
      />
      <circle cx="14" cy="14" r="6" fill="white" opacity="0.95" />
    </svg>
  );
}

/* ── Popup content ───────────────────────────────────────────────────────── */

function PopupContent({ pin, onClose }: { pin: DoctorPin; onClose: () => void }) {
  return (
    <div className="w-52 p-3">
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="flex-1 min-w-0">
          <p className="font-semibold text-slate-800 text-sm leading-tight truncate">{pin.name}</p>
          {pin.specialty && (
            <p className="text-xs text-indigo-600 font-medium capitalize mt-0.5">{pin.specialty}</p>
          )}
        </div>
        <button
          onClick={onClose}
          className="p-0.5 rounded hover:bg-slate-100 shrink-0 transition-colors"
        >
          <X size={12} className="text-slate-400" />
        </button>
      </div>

      <div className="space-y-1">
        {pin.address && (
          <p className="text-xs text-slate-500 leading-snug">{pin.address}</p>
        )}
        {pin.phone && (
          <div className="flex items-center gap-1.5 text-xs text-slate-500">
            <Phone size={10} className="shrink-0" />
            <span>{pin.phone}</span>
          </div>
        )}
        {pin.rating !== undefined && (
          <div className="flex items-center gap-1 text-xs text-amber-600 font-medium">
            <Star size={10} className="fill-amber-400 text-amber-400" />
            {pin.rating.toFixed(1)}
          </div>
        )}
        {pin.is_open_now !== undefined && (
          <p className={cn("text-xs font-semibold", pin.is_open_now ? "text-emerald-600" : "text-slate-400")}>
            {pin.is_open_now ? "● Open now" : "● Closed"}
          </p>
        )}
      </div>
    </div>
  );
}

/* ── Main component ──────────────────────────────────────────────────────── */

interface Props {
  pins: DoctorPin[];
  selectedId: string | null;
  onSelectPin: (pin: DoctorPin) => void;
  userLocation?: { lat: number; lng: number };
}

export default function MapClient({ pins, selectedId, onSelectPin, userLocation }: Props) {
  /* true once the maplibre-gl WebGL context has finished initialising */
  const [mapLoaded, setMapLoaded] = useState(false);
  const [popupPin, setPopupPin]   = useState<DoctorPin | null>(null);
  const mapRef                    = useRef<MapRef>(null);

  /* Filter pins to those with finite, non-zero coordinates.
     Any pin that slipped through with NaN / Infinity would crash fitBounds. */
  const validPins = useMemo(() => {
    const result = pins.filter(
      (p) => Number.isFinite(p.lat) && Number.isFinite(p.lng)
    );
    console.log(
      "[MAP FLOW] rendering markers",
      result.length,
      "of",
      pins.length,
      result
    );
    return result;
  }, [pins]);

  /* ── Fit bounds ─────────────────────────────────────────────────────────── *
   * This effect depends on BOTH `mapLoaded` and `validPins`, which covers
   * two distinct timing cases:
   *
   *   Case A — Navigation from /patient → /patient/map while pins are already
   *             in the store: the map mounts, `mapLoaded` flips true, and the
   *             effect runs with the existing pins.
   *
   *   Case B — User searches from within the map page: `validPins` updates
   *             while `mapLoaded` is already true, so the effect re-runs.
   *
   * The old code only depended on `[pins]` which caused Case A to fail because
   * `mapRef.current?.getMap()` was null on the very first run (GL context not
   * yet ready), and the effect never re-ran since `pins` didn't change again.
   * ──────────────────────────────────────────────────────────────────────── */
  useEffect(() => {
    if (!mapLoaded || !validPins.length) return;

    const map = mapRef.current?.getMap();
    if (!map) return;

    console.log("[MAP FLOW] map center (before fit)", map.getCenter());

    if (validPins.length === 1) {
      map.easeTo({
        center:   [validPins[0].lng, validPins[0].lat],
        zoom:     15,
        duration: 600,
      });
      return;
    }

    const lngs = validPins.map((p) => p.lng);
    const lats  = validPins.map((p) => p.lat);
    map.fitBounds(
      [
        [Math.min(...lngs), Math.min(...lats)],
        [Math.max(...lngs), Math.max(...lats)],
      ],
      { padding: 80, maxZoom: 15, duration: 600 }
    );
  }, [mapLoaded, validPins]);

  const handleMapLoad = useCallback(() => {
    console.log("[MAP FLOW] map loaded — GL context ready");
    setMapLoaded(true);
  }, []);

  const handleMarkerClick = useCallback(
    (pin: DoctorPin) => {
      onSelectPin(pin);
      setPopupPin(pin);
    },
    [onSelectPin]
  );

  /* MapClient is loaded with `dynamic(..., { ssr: false })` so we never run
     on the server. The old `mounted` state guard was redundant — removed. */
  return (
    <Map
      ref={mapRef}
      initialViewState={INITIAL_VIEW}
      mapStyle={MAP_STYLE}
      style={{ width: "100%", height: "100%" }}
      onLoad={handleMapLoad}
    >
      <NavigationControl position="bottom-right" />

      {/* User location — blue pulsing dot */}
      {userLocation && (
        <Marker
          latitude={userLocation.lat}
          longitude={userLocation.lng}
          anchor="center"
        >
          <div className="relative flex h-5 w-5 items-center justify-center">
            <div className="absolute h-5 w-5 rounded-full bg-blue-400/40 animate-ping" />
            <div className="h-3 w-3 rounded-full bg-blue-500 border-2 border-white shadow-md" />
          </div>
        </Marker>
      )}

      {/* Doctor pins — only rendered after the GL context is ready so the
          maplibre projection is available and markers land at correct pixels. */}
      {mapLoaded &&
        validPins.map((pin) => (
          <Marker
            key={pin.id}
            latitude={pin.lat}
            longitude={pin.lng}
            anchor="bottom"
            onClick={() => handleMarkerClick(pin)}
          >
            <PinSvg specialty={pin.specialty} selected={pin.id === selectedId} />
          </Marker>
        ))}

      {popupPin && (
        <Popup
          latitude={popupPin.lat}
          longitude={popupPin.lng}
          anchor="bottom"
          offset={42}
          onClose={() => setPopupPin(null)}
          closeButton={false}
          className="clinix-map-popup"
        >
          <PopupContent pin={popupPin} onClose={() => setPopupPin(null)} />
        </Popup>
      )}
    </Map>
  );
}
