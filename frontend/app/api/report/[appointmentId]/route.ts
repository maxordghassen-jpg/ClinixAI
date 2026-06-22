import { NextRequest } from "next/server";
import { AGENT_URL, proxy } from "@/lib/proxy";

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ appointmentId: string }> }
) {
  const { appointmentId } = await params;
  return proxy(`${AGENT_URL}/reports/appointment/${appointmentId}`, {
    headers: { Authorization: req.headers.get("authorization") ?? "" },
  });
}
