import { NextRequest } from "next/server";
import { AUTH_URL, proxy } from "@/lib/proxy";

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ patientId: string }> }
) {
  const { patientId } = await params;
  const auth = req.headers.get("authorization") ?? "";
  return proxy(`${AUTH_URL}/patients/${patientId}/profile`, {
    method: "GET",
    headers: { Authorization: auth },
  });
}
