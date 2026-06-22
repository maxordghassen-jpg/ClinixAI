import { NextRequest } from "next/server";
import { AUTH_URL, proxy } from "@/lib/proxy";

export async function POST(req: NextRequest) {
  return proxy(`${AUTH_URL}/auth/login`, {
    method: "POST",
    body: await req.text(),
  });
}
