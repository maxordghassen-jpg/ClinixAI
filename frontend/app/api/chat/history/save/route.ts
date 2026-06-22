import { NextRequest } from "next/server";
import { AGENT_URL, proxy } from "@/lib/proxy";

export async function POST(req: NextRequest) {
  const auth = req.headers.get("authorization") ?? "";
  const body = await req.text();
  return proxy(`${AGENT_URL}/chat/history/save`, {
    method: "POST",
    body,
    headers: { Authorization: auth },
  });
}
