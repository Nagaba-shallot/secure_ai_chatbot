import { NextResponse } from "next/server";

export const BACKEND_URL = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";
export const COOKIE_NAME = "nasha_token";

export const cookieOptions = (maxAge = 60 * 60 * 24 * 30) => ({
  httpOnly: true,
  sameSite: "lax",
  secure: process.env.NODE_ENV === "production",
  path: "/",
  maxAge,
});

export function forwardHeaders(req, base = {}) {
  const headers = { ...base };
  const incoming = req.headers.get("x-forwarded-for");
  const last = incoming ? incoming.split(",").pop().trim() : "";
  if (last) headers["X-Forwarded-For"] = last;
  return headers;
}

/** Basic CSRF defence for state-changing requests: the Origin must match our own host. */
export function sameOriginOrReject(req) {
  const origin = req.headers.get("origin");
  if (origin) {
    try {
      if (new URL(origin).host !== req.headers.get("host")) {
        return NextResponse.json({ detail: "Cross-origin request blocked" }, { status: 403 });
      }
    } catch {
      return NextResponse.json({ detail: "Bad origin" }, { status: 403 });
    }
  }
  return null;
}

/** Forward a request to the backend using the token from the httpOnly cookie. */
export async function proxy(req, path, { method, body }) {
  const token = req.cookies.get(COOKIE_NAME)?.value;
  if (!token) {
    return NextResponse.json({ detail: "No session" }, { status: 401 });
  }

  let upstream;
  try {
    upstream = await fetch(`${BACKEND_URL}${path}`, {
      method,
      headers: forwardHeaders(req, { Authorization: `Bearer ${token}`, "Content-Type": "application/json" }),
      body,
      cache: "no-store",
    });
  } catch {
    return NextResponse.json({ detail: "The companion service is not reachable" }, { status: 502 });
  }

  if (upstream.status === 204) {
    return new NextResponse(null, { status: 204 });
  }
  const data = await upstream.json().catch(() => ({ detail: "Unexpected response from the service" }));
  const res = NextResponse.json(data, { status: upstream.status });
  const retryAfter = upstream.headers.get("retry-after");
  if (retryAfter) res.headers.set("Retry-After", retryAfter);
  return res;
}

/** Like proxy(), but passes a streaming (NDJSON) reply straight through to the browser. */
export async function proxyStream(req, path, body) {
  const token = req.cookies.get(COOKIE_NAME)?.value;
  if (!token) {
    return NextResponse.json({ detail: "No session" }, { status: 401 });
  }

  let upstream;
  try {
    upstream = await fetch(`${BACKEND_URL}${path}`, {
      method: "POST",
      headers: forwardHeaders(req, { Authorization: `Bearer ${token}`, "Content-Type": "application/json" }),
      body,
      cache: "no-store",
    });
  } catch {
    return NextResponse.json({ detail: "The companion service is not reachable" }, { status: 502 });
  }

  if (!upstream.ok || !upstream.body) {
    const data = await upstream.json().catch(() => ({ detail: "Unexpected response from the service" }));
    const res = NextResponse.json(data, { status: upstream.status });
    const retryAfter = upstream.headers.get("retry-after");
    if (retryAfter) res.headers.set("Retry-After", retryAfter);
    return res;
  }

  return new Response(upstream.body, {
    status: 200,
    headers: { "Content-Type": "application/x-ndjson", "Cache-Control": "no-store, no-transform" },
  });
}


export async function authProxy(req, path, payload, { sendToken = false } = {}) {
  const headers = forwardHeaders(req, { "Content-Type": "application/json" });
  if (sendToken) {
    const current = req.cookies.get(COOKIE_NAME)?.value;
    if (current) headers.Authorization = `Bearer ${current}`;
  }

  let upstream;
  try {
    upstream = await fetch(`${BACKEND_URL}${path}`, {
      method: "POST",
      headers,
      body: JSON.stringify(payload),
      cache: "no-store",
    });
  } catch {
    return NextResponse.json({ detail: "The companion service is not reachable" }, { status: 502 });
  }

  const data = await upstream.json().catch(() => ({ detail: "Unexpected response from the service" }));
  if (!upstream.ok) {
    const detail = typeof data.detail === "string" ? data.detail : "Something went wrong";
    const res = NextResponse.json({ detail }, { status: upstream.status });
    const retryAfter = upstream.headers.get("retry-after");
    if (retryAfter) res.headers.set("Retry-After", retryAfter);
    return res;
  }

  const res = NextResponse.json({ user_id: data.user_id, email: data.email ?? null });
  res.cookies.set(COOKIE_NAME, data.token, cookieOptions());
  return res;
}