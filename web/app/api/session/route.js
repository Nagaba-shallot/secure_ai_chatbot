import { NextResponse } from "next/server";
import { BACKEND_URL, COOKIE_NAME, cookieOptions, forwardHeaders, sameOriginOrReject } from "@/lib/backend";

export async function POST(req) {
  const blocked = sameOriginOrReject(req);
  if (blocked) return blocked;

  let upstream;
  try {
    upstream = await fetch(`${BACKEND_URL}/auth/register`, { method: "POST", headers: forwardHeaders(req), cache: "no-store" });
  } catch {
    return NextResponse.json({ detail: "The companion service is not reachable" }, { status: 502 });
  }
  if (!upstream.ok) {
    const data = await upstream.json().catch(() => ({ detail: "Could not start a session" }));
    const res = NextResponse.json(data, { status: upstream.status });
    const retryAfter = upstream.headers.get("retry-after");
    if (retryAfter) res.headers.set("Retry-After", retryAfter);
    return res;
  }

  const { token } = await upstream.json();
  const res = NextResponse.json({ ok: true });
  res.cookies.set(COOKIE_NAME, token, cookieOptions());
  return res;
}