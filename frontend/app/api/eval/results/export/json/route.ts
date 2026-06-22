import { NextRequest } from "next/server";
import { EVAL_URL } from "@/lib/proxy";

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const qs = searchParams.toString();
  const upstream = qs
    ? `${EVAL_URL}/results/export/json?${qs}`
    : `${EVAL_URL}/results/export/json`;

  const res  = await fetch(upstream, { method: "GET" });
  const body = await res.arrayBuffer();
  return new Response(body, {
    status:  res.status,
    headers: {
      "Content-Type":        "application/json",
      "Content-Disposition": "attachment; filename=eval_results.json",
    },
  });
}
