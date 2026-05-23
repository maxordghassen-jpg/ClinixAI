import { NextRequest } from "next/server";
import { AGENT_URL, proxy } from "@/lib/proxy";

export async function POST(req: NextRequest) {
  return proxy(`${AGENT_URL}/patient/chat`, {
    method: "POST",
    body: await req.text(),
  });
}
