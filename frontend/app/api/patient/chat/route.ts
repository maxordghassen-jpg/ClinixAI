import { NextRequest } from "next/server";
import { AGENT_URL, proxy } from "@/lib/proxy";

export async function POST(req: NextRequest) {
  const url = `${AGENT_URL}/patient/chat`;
  console.log("CHAT_URL", url);
  return proxy(url, {
    method: "POST",
    body: await req.text(),
  });
}
