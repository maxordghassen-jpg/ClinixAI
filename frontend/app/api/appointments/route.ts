import { NextRequest } from "next/server";
import { APPT_URL, proxy } from "@/lib/proxy";

export async function POST(req: NextRequest) {
  return proxy(`${APPT_URL}/appointments`, {
    method: "POST",
    body: await req.text(),
  });
}
