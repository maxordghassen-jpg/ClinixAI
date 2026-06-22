import { NextRequest } from "next/server";
import { AGENT_URL, proxy } from "@/lib/proxy";

type Params = Promise<{ userRole: string; userId: string }>;

export async function GET(req: NextRequest, { params }: { params: Params }) {
  const { userRole, userId } = await params;
  const auth = req.headers.get("authorization") ?? "";
  try {
    return await proxy(`${AGENT_URL}/chat/history/${userRole}/${userId}`, {
      method: "GET",
      headers: { Authorization: auth },
    });
  } catch {
    // Agent service unreachable — return empty list so the sidebar degrades silently
    return new Response("[]", { status: 200, headers: { "Content-Type": "application/json" } });
  }
}

export async function DELETE(req: NextRequest, { params }: { params: Params }) {
  const { userRole, userId } = await params;
  const auth = req.headers.get("authorization") ?? "";
  try {
    return await proxy(`${AGENT_URL}/chat/history/${userRole}/${userId}`, {
      method: "DELETE",
      headers: { Authorization: auth },
    });
  } catch {
    return new Response(null, { status: 204 });
  }
}
