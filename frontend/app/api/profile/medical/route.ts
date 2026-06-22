import { NextRequest } from "next/server";
import { AUTH_URL, proxy } from "@/lib/proxy";

export async function PATCH(req: NextRequest) {
  const auth = req.headers.get("authorization") ?? "";
  return proxy(`${AUTH_URL}/profile/medical`, {
    method: "PATCH",
    body: await req.text(),
    headers: { Authorization: auth },
  });
}
