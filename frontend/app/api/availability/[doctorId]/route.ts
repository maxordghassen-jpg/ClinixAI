import { NextRequest } from "next/server";
import { AVAIL_URL, proxy } from "@/lib/proxy";

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ doctorId: string }> }
) {
  const { doctorId } = await params;
  return proxy(`${AVAIL_URL}/availability/${doctorId}`);
}
