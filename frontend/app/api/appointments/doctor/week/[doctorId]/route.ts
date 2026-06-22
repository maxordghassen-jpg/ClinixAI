import { NextRequest } from "next/server";
import { APPT_URL, proxy } from "@/lib/proxy";

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ doctorId: string }> }
) {
  const { doctorId } = await params;
  return proxy(`${APPT_URL}/appointments/week/${doctorId}`);
}
