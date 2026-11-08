import { NextResponse } from "next/server";
import { proxy } from "@/lib/backend";

export const dynamic = "force-dynamic";

export async function GET(req) {
  const params = req.nextUrl.searchParams;
  const days = params.get("days") ?? "14";
  const scope = params.get("scope") ?? "me";
  if (!/^\d{1,2}$/.test(days) || !["me", "all"].includes(scope)) {
    return NextResponse.json({ detail: "Invalid request" }, { status: 400 });
  }
  return proxy(req, `/stats?days=${days}&scope=${scope}`, { method: "GET" });
}