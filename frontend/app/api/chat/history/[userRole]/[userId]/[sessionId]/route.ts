import { NextRequest } from "next/server";
import { AGENT_URL, proxy } from "@/lib/proxy";

type Params = Promise<{ userRole: string; userId: string; sessionId: string }>;

export async function GET(req: NextRequest, { params }: { params: Params }) {
  const { userRole, userId, sessionId } = await params;
  const auth = req.headers.get("authorization") ?? "";
  try {
    return await proxy(`${AGENT_URL}/chat/history/${userRole}/${userId}/${sessionId}`, {
      method: "GET",
      headers: { Authorization: auth },
    });
  } catch {
    return new Response('{"detail":"Not found"}', { status: 404, headers: { "Content-Type": "application/json" } });
  }
}

export async function DELETE(req: NextRequest, { params }: { params: Params }) {
  const { userRole, userId, sessionId } = await params;
  const auth = req.headers.get("authorization") ?? "";
  try {
    return await proxy(`${AGENT_URL}/chat/history/${userRole}/${userId}/${sessionId}`, {
      method: "DELETE",
      headers: { Authorization: auth },
    });
  } catch {
    return new Response(null, { status: 204 });
  }
}
