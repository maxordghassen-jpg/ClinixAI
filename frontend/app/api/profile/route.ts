import { NextRequest } from "next/server";
import { AUTH_URL, proxy } from "@/lib/proxy";

export async function GET(req: NextRequest) {
  const auth = req.headers.get("authorization") ?? "";
  return proxy(`${AUTH_URL}/profile`, {
    method: "GET",
    headers: { Authorization: auth },
  });
}

export async function PUT(req: NextRequest) {
  const auth = req.headers.get("authorization") ?? "";
  return proxy(`${AUTH_URL}/profile`, {
    method: "PUT",
    body: await req.text(),
    headers: { Authorization: auth },
  });
}
