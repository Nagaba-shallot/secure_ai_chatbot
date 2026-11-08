import { proxy } from "@/lib/backend";

export async function GET(req) {
  return proxy(req, "/history?limit=50", { method: "GET" });
}