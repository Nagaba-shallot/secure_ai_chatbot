import { NextResponse } from "next/server";
import { COOKIE_NAME, proxy, sameOriginOrReject } from "@/lib/backend";

export async function POST(req) {
  const blocked = sameOriginOrReject(req);
  if (blocked) return blocked;

  await proxy(req, "/auth/logout", { method: "POST" }).catch(() => null);
  const res = new NextResponse(null, { status: 204 });
  res.cookies.set(COOKIE_NAME, "", { httpOnly: true, path: "/", maxAge: 0 });
  return res;
}