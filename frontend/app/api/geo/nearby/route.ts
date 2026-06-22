import { NextRequest } from "next/server";
import { GEO_URL, proxy } from "@/lib/proxy";

export async function POST(req: NextRequest) {
  return proxy(`${GEO_URL}/api/nearby`, {
    method: "POST",
    body: await req.text(),
  });
}
