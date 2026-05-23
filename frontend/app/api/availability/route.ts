import { NextRequest } from "next/server";
import { AVAIL_URL, proxy } from "@/lib/proxy";

export async function POST(req: NextRequest) {
  return proxy(`${AVAIL_URL}/availability`, {
    method: "POST",
    body: await req.text(),
  });
}
