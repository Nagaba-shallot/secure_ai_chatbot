import { NextResponse } from "next/server";
import { authProxy, sameOriginOrReject } from "@/lib/backend";

export async function POST(req) {
  const blocked = sameOriginOrReject(req);
  if (blocked) return blocked;

  let email;
  let password;
  try {
    ({ email, password } = await req.json());
  } catch {
    return NextResponse.json({ detail: "Invalid request" }, { status: 400 });
  }
  if (typeof email !== "string" || typeof password !== "string" || email.length > 254 || password.length > 128) {
    return NextResponse.json({ detail: "Enter a valid email and password." }, { status: 400 });
  }
  return authProxy(req, "/auth/signup", { email, password }, { sendToken: true });
}