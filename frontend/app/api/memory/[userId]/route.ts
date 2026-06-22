import { NextRequest } from "next/server";
import { AGENT_URL, proxy } from "@/lib/proxy";

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ userId: string }> }
) {
  const { userId } = await params;
  const auth = req.headers.get("authorization") ?? "";
  return proxy(`${AGENT_URL}/memory/user/${userId}`, {
    method: "GET",
    headers: { Authorization: auth },
  });
}
