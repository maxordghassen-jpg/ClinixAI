import { NextRequest } from "next/server";
import { EVAL_URL, proxy } from "@/lib/proxy";

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  return proxy(`${EVAL_URL}/results/${id}`, { method: "GET" });
}

export async function DELETE(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  return proxy(`${EVAL_URL}/results/${id}`, { method: "DELETE" });
}
