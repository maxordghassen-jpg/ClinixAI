// Shared proxy helper — forward a request to the upstream backend service
// and stream the response back as-is.

export const AGENT_URL =
  process.env.AGENT_SERVICE_URL ?? "http://localhost:8001";
export const APPT_URL =
  process.env.APPOINTMENT_SERVICE_URL ?? "http://localhost:8003";
export const AVAIL_URL =
  process.env.AVAILABILITY_SERVICE_URL ?? "http://localhost:8002";

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
  const body = await res.text();
  return new Response(body, {
    status: res.status,
    headers: { "Content-Type": "application/json" },
  });
}
