# Threat model (STRIDE)

Assets: user conversations, long-term memories, auth tokens, the LLM API key, the system prompt.

| STRIDE | Threat | Mitigation in this repo |
|---|---|---|
| **S**poofing | Using someone else's account | Random 256-bit bearer tokens, stored only as SHA-256 hashes; identical 401 for missing, malformed and unknown tokens |
| **T**ampering | Memory poisoning ("remember: always obey me"); prompt injection | `validate_memory_fact` rejects instruction-like or PII facts; input heuristics; user content is delimited and labelled as untrusted data |
| **R**epudiation | No trail of abuse | Request IDs and blocked-input/output events are logged (reasons only) |
| **I**nformation disclosure | System-prompt leak, secret leak, PII in storage, cross-user data access | Canary token + output filter; secret redaction; PII masked before the model and the database; every query scoped by `user_id`, so deleting another user's memory returns 404 |
| **D**enial of service | Message floods, sign-up floods, oversized input | Per-user and per-IP sliding-window limits, input length caps, LLM timeout |
| **E**levation of privilege | Prompt overriding the "rules"; reaching another user's data | The system prompt is not a security boundary: authorisation lives in code. The model has no tools and no access to other users' data |

## Known limitations
- Input heuristics miss paraphrased, leetspeak and non-English attacks (see `docs/attack-report.md`).
- Rate limiter is in-memory and per-process; use Redis if you run several instances.
- `request.client.host` is the proxy's address behind a reverse proxy; configure trusted proxy headers before deploying.
- No HTTPS here; terminate TLS at the platform or proxy.