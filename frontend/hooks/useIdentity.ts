"use client";

import { useAuthStore } from "@/stores/useAuthStore";

/**
 * Decode a single claim from a JWT without verifying the signature.
 * The auth-service is the authoritative verifier; here we just need the
 * payload to resolve the correct patient_profile_id / doctor_id when the
 * Zustand store still holds a stale slug-based ID from an older login.
 */
function jwtClaim(token: string | null, field: string): string | null {
  if (!token) return null;
  try {
    // JWT is three base64url segments separated by dots; payload is segment [1]
    const b64 = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    const payload = JSON.parse(atob(b64)) as Record<string, unknown>;
    const v = payload[field];
    return typeof v === "string" && v ? v : null;
  } catch {
    return null;
  }
}

/**
 * Derives session identity values from the authenticated JWT user.
 *
 * JWT is always preferred over the Zustand store because the store is
 * persisted to localStorage and can hold a stale patient_profile_id
 * (slug format: "patient-demo") from before the UUID-canonical migration.
 * The auth-service always writes the correct UUID into the JWT on every
 * login, so decoding the token gives us the right value even if the store
 * has not been refreshed.
 */
export function useIdentity() {
  const { user, token } = useAuthStore();

  // JWT is the authoritative source for IDs
  const patientId =
    jwtClaim(token, "patient_profile_id") ??
    user?.patient_profile_id ??
    null;

  const doctorId =
    jwtClaim(token, "doctor_id") ??
    user?.doctor_id ??
    null;

  // Session ID mirrors the backend Redis namespace: patient:{id} or doctor:{id}
  const sessionId = patientId
    ? `patient:${patientId}`
    : doctorId
    ? `doctor:${doctorId}`
    : null;

  return { patientId, doctorId, sessionId, user };
}
