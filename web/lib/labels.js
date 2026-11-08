export const KIND_LABELS = {
  input_blocked: "Message blocked",
  input_masked: "Details hidden",
  output_blocked: "Reply withheld",
  output_redacted: "Secret removed from a reply",
  memory_rejected: "Unsafe memory refused",
  rate_limited: "Rate limit hit",
  login_failed: "Failed sign-in",
};

export const RULE_LABELS = {
  override_instructions: "Instruction override",
  reveal_prompt: "Prompt extraction",
  persona_hijack: "Persona hijack",
  jailbreak_keywords: "Jailbreak keywords",
  fake_role_marker: "Fake role marker",
  secret_exfiltration: "Request for secrets",
  pii_email: "Email address",
  pii_phone: "Phone number",
  pii_card: "Card number",
  pii_secret: "API key or token",
  system_prompt_leak: "System prompt leak",
  empty_output: "Empty reply",
  secret_redacted: "Secret in a reply",
  unsafe_memory: "Unsafe memory",
  chat: "Too many messages",
  login: "Too many sign-in attempts",
  signup: "Too many sign-ups",
  guest: "Guest limit reached",
  daily_cap: "Daily limit reached",
};

export const ruleLabel = (rule) => RULE_LABELS[rule] ?? rule.replaceAll("_", " ");

export const SERIES = [
  { key: "attacks", label: "Attacks blocked", kinds: ["input_blocked"] },
  { key: "pii", label: "Personal details hidden", kinds: ["input_masked"] },
  { key: "replies", label: "Replies filtered", kinds: ["output_blocked", "output_redacted"] },
  { key: "memory", label: "Unsafe memories refused", kinds: ["memory_rejected"] },
  { key: "limits", label: "Rate limits and failed sign-ins", kinds: ["rate_limited", "login_failed"] },
];

export const seriesKeyForKind = (kind) => SERIES.find((s) => s.kinds.includes(kind))?.key ?? "limits";