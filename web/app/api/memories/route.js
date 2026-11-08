import { NextResponse } from "next/server";
import { proxy, sameOriginOrReject } from "@/lib/backend";

export async function GET(req) {
  return proxy(req, "/memories", { method: "GET" });
}

export async function DELETE(req) {
  const blocked = sameOriginOrReject(req);
  if (blocked) return blocked;

  const id = req.nextUrl.searchParams.get("id") ?? "";
  if (!/^\d{1,9}$/.test(id)) {
    return NextResponse.json({ detail: "Invalid memory id" }, { status: 400 });
  }
  return proxy(req, `/memories/${id}`, { method: "DELETE" });
}