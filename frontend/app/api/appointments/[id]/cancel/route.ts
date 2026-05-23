import { NextRequest } from "next/server";
import { APPT_URL, proxy } from "@/lib/proxy";

export async function POST(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  return proxy(`${APPT_URL}/appointments/${id}/cancel`, { method: "POST" });
}
