import { NextResponse } from "next/server";
import { proxy, sameOriginOrReject } from "@/lib/backend";

export async function POST(req) {
  const blocked = sameOriginOrReject(req);
  if (blocked) return blocked;

  let message;
  try {
    ({ message } = await req.json());
  } catch {
    return NextResponse.json({ detail: "Invalid request" }, { status: 400 });
  }
  if (typeof message !== "string" || !message.trim() || message.length > 4000) {
    return NextResponse.json({ detail: "Message is empty or too long" }, { status: 400 });
  }
  return proxy(req, "/chat", { method: "POST", body: JSON.stringify({ message }) });
}