import { NextRequest } from "next/server";
import { EVAL_URL, proxy } from "@/lib/proxy";

export async function POST(req: NextRequest) {
  const body = await req.text();
  return proxy(`${EVAL_URL}/results/compare`, { method: "POST", body });
}
