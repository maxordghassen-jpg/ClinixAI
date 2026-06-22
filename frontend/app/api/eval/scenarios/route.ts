import { NextRequest } from "next/server";
import { EVAL_URL, proxy } from "@/lib/proxy";

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const params = searchParams.toString();
  const url    = params ? `${EVAL_URL}/scenarios?${params}` : `${EVAL_URL}/scenarios`;
  return proxy(url, { method: "GET" });
}
