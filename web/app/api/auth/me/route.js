import { proxy } from "@/lib/backend";

export async function GET(req) {
  return proxy(req, "/auth/me", { method: "GET" });
}