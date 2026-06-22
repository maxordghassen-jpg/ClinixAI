import { NextRequest } from "next/server";
import { EVAL_URL, proxy } from "@/lib/proxy";

export async function POST(
  _req: NextRequest,
  { params }: { params: Promise<{ scenarioId: string }> }
) {
  const { scenarioId } = await params;
  return proxy(`${EVAL_URL}/run/${scenarioId}`, { method: "POST" });
}
