import { NextRequest } from "next/server";
import { APPT_URL, proxy } from "@/lib/proxy";

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ patientId: string }> }
) {
  const { patientId } = await params;
  return proxy(`${APPT_URL}/appointments/patient/week/${patientId}`);
}
