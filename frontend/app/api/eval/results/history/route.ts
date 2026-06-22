import { NextRequest } from "next/server";
import { EVAL_URL, proxy } from "@/lib/proxy";

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const qs = searchParams.toString();
  return proxy(qs ? `${EVAL_URL}/results/history?${qs}` : `${EVAL_URL}/results/history`, { method: "GET" });
}
