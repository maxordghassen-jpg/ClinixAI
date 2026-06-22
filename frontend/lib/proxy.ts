// Shared proxy helper — forward a request to the upstream backend service
// and stream the response back as-is.

export const AGENT_URL =
  process.env.AGENT_SERVICE_URL ?? "http://localhost:8001";
export const APPT_URL =
  process.env.APPOINTMENT_SERVICE_URL ?? "http://localhost:8003";
export const AVAIL_URL =
  process.env.AVAILABILITY_SERVICE_URL ?? "http://localhost:8002";
export const GEO_URL =
  process.env.GEO_SERVICE_URL ?? "http://localhost:5000";
export const AUTH_URL =
  process.env.AUTH_SERVICE_URL ?? "http://localhost:8005";
export const EVAL_URL =
  process.env.EVAL_SERVICE_URL ?? "http://localhost:8006";

// Statuses that must have a null body per the Fetch spec.
// The Response constructor throws TypeError if you pass a non-null body
// with one of these statuses (e.g. new Response("", { status: 204 }) throws).
const NULL_BODY_STATUSES = new Set([101, 204, 205, 304]);

export async function proxy(
  upstream: string,
  init: RequestInit = {}
): Promise<Response> {
  const res = await fetch(upstream, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init.headers as Record<string, string>),
    },
  });

  if (NULL_BODY_STATUSES.has(res.status)) {
    // Must use null body — non-null body with these statuses throws TypeError
    return new Response(null, { status: res.status });
  }

  const body = await res.text();
  return new Response(body, {
    status: res.status,
    headers: { "Content-Type": "application/json" },
  });
}
