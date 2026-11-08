export class ApiError extends Error {
  constructor(message, status, retryAfter, code) {
    super(message);
    this.status = status;
    this.retryAfter = retryAfter;
    this.code = code; // e.g. "guest_limit" or "daily_cap"
  }
}

async function call(url, init = {}) {
  return fetch(url, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init.headers ?? {}) },
    credentials: "same-origin",
    cache: "no-store",
  });
}

async function parse(res) {
  if (res.ok) {
    return res.status === 204 ? undefined : await res.json();
  }
  const body = await res.json().catch(() => ({}));
  const retry = Number(res.headers.get("Retry-After")) || undefined;
  // `detail` is a plain message, or { code, message } for errors the page reacts to
  const detail = body.detail;
  const message = typeof detail === "string" ? detail : (detail?.message ?? "Something went wrong");
  throw new ApiError(message, res.status, retry, typeof detail === "object" ? detail?.code : undefined);
}

async function createSession() {
  await parse(await call("/api/session", { method: "POST" }));
}

async function withSession(run) {
  let res = await run();
  if (res.status === 401) {
    await createSession();
    res = await run();
  }
  return parse(res);
}


export async function streamMessage(message, onEvent) {
  const run = () => call("/api/chat/stream", { method: "POST", body: JSON.stringify({ message }) });
  let res = await run();
  if (res.status === 401) {
    await createSession();
    res = await run();
  }
  if (!res.ok) await parse(res); // throws an ApiError with the right status and message
  if (!res.body) throw new ApiError("Streaming is not supported in this browser", 500);

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let newline;
    while ((newline = buffer.indexOf("\n")) >= 0) {
      const line = buffer.slice(0, newline).trim();
      buffer = buffer.slice(newline + 1);
      if (!line) continue;
      const event = JSON.parse(line);
      if (event.type === "error") throw new ApiError(event.detail || "Couldn't get a reply", 502);
      onEvent(event);
    }
  }
}

export const AUTH_EVENT = "auth-changed";
const notifyAuthChanged = () => {
  if (typeof window !== "undefined") window.dispatchEvent(new Event(AUTH_EVENT));
};

/** The current account: { user_id, email, anonymous }, or null when there is no session yet. */
export async function getMe() {
  const res = await call("/api/auth/me");
  if (res.status === 401) return null;
  return parse(res);
}

export async function signUp(email, password) {
  const result = await parse(await call("/api/auth/signup", { method: "POST", body: JSON.stringify({ email, password }) }));
  notifyAuthChanged();
  return result;
}

export async function signIn(email, password) {
  const result = await parse(await call("/api/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }));
  notifyAuthChanged();
  return result;
}

export async function signOut() {
  await call("/api/auth/logout", { method: "POST" }).catch(() => null);
  notifyAuthChanged();
}

export async function loadStats(days = 14, scope = "me") {
  const res = await call(`/api/stats?days=${days}&scope=${scope}`);
  if (res.status === 401) return { days, scope, totals: {}, daily: [], rules: [], recent: [] }; // no session yet
  return parse(res);
}

export const loadHistory = () => withSession(() => call("/api/history"));

export const sendMessage = (message) =>
  withSession(() => call("/api/chat", { method: "POST", body: JSON.stringify({ message }) }));

export async function loadMemories() {
  const res = await call("/api/memories");
  if (res.status === 401) return []; // no session yet, so nothing is remembered
  return parse(res);
}

export const forgetMemory = async (id) => parse(await call(`/api/memories?id=${id}`, { method: "DELETE" }));

export const deleteEverything = async () => parse(await call("/api/me", { method: "DELETE" }));

export function describeError(err) {
  if (err instanceof ApiError) {
    if (err.code === "guest_limit" || err.code === "daily_cap") return err.message;
    if (err.status === 429) {
      return `You're sending messages quickly. Try again in ${err.retryAfter ?? "a few"} seconds.`;
    }
    if (err.status === 502) {
      return "Nasha couldn't reply just now. Check that the backend is running, then try again.";
    }
    if (err.status === 400) return "That message is empty or too long (4,000 characters at most).";
    return err.message;
  }
  return "Something went wrong. Try again.";
}