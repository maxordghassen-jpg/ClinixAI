import { NextRequest } from "next/server";
import { AUTH_URL, proxy } from "@/lib/proxy";

export async function GET(req: NextRequest) {
  const auth = req.headers.get("authorization") ?? "";
  return proxy(`${AUTH_URL}/auth/me`, {
    method: "GET",
    headers: { Authorization: auth },
  });
}
