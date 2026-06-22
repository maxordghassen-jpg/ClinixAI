import { NextRequest } from "next/server";
import { AGENT_URL, proxy } from "@/lib/proxy";

export async function POST(req: NextRequest) {
  const auth = req.headers.get("authorization") ?? "";
  return proxy(`${AGENT_URL}/chat/history/save`, {
    method: "POST",
    body: await req.text(),
    headers: { Authorization: auth },
  });
}
