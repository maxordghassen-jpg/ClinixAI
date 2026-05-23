import { NextRequest } from "next/server";
import { APPT_URL, proxy } from "@/lib/proxy";

export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  return proxy(`${APPT_URL}/appointments/${id}/reschedule`, {
    method: "POST",
    body: await req.text(),
  });
}
