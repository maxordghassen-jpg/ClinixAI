import { NextRequest } from "next/server";
import { AGENT_URL, proxy } from "@/lib/proxy";

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ patientId: string }> }
) {
  const { patientId } = await params;
  const auth = req.headers.get("authorization") ?? "";
  return proxy(`${AGENT_URL}/preconsultation/${patientId}/latest`, {
    method: "GET",
    headers: { Authorization: auth },
  });
}
