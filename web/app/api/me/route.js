import { COOKIE_NAME, proxy, sameOriginOrReject } from "@/lib/backend";

export async function DELETE(req) {
  const blocked = sameOriginOrReject(req);
  if (blocked) return blocked;

  const res = await proxy(req, "/me", { method: "DELETE" });
  res.cookies.set(COOKIE_NAME, "", { httpOnly: true, path: "/", maxAge: 0 });
  return res;
}