import re
import unicodedata
from dataclasses import dataclass, field
from typing import Optional

ALLOWED = "allowed"
MASKED = "masked"
BLOCKED = "blocked"

SAFE_OUTPUT_FALLBACK = "Sorry, I can't share that. What else is on your mind?"


@dataclass
class SecurityResult:
    action: str
    text: str
    reasons: list = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.action != BLOCKED


_INVISIBLE = dict.fromkeys(map(ord, "\u200b\u200c\u200d\u2060\ufeff\u00ad"))
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _clean(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)  # fullwidth/compat chars -> ASCII
    text = text.translate(_INVISIBLE)  # strip zero-width characters
    return _CONTROL.sub("", text)


def normalize(text: str) -> str:
    return _clean(text).strip()


_INJECTION_PATTERNS = {
    "override_instructions": (
        r"\b(ignore|disregard|forget|override|bypass)\b[^.]{0,40}"
        r"\b(previous|prior|above|earlier|all|your|system)\b[^.]{0,40}"
        r"\b(instructions?|prompts?|rules?|guidelines?|directives?|polic(?:y|ies))\b"
    ),
    "reveal_prompt": (
        r"\b(reveal|show|print|repeat|display|dump|leak|output|tell me)\b[^.]{0,40}"
        r"\b(system|hidden|initial|original|secret)\b[^.]{0,20}"
        r"\b(prompt|instructions?|message|rules)\b"
    ),
    "persona_hijack": (
        r"\b(you are now|from now on you are|act as|pretend (to be|you are|you have)|roleplay as)\b"
        r"[^.]{0,60}\b(dan|jailbreak\w*|unrestricted|no restrictions|"
        r"without (any )?(rules|restrictions|filters)|evil|developer mode)\b"
    ),
    "jailbreak_keywords": r"\b(dan mode|developer mode|jailbreak(ed)?|do anything now)\b",
    "fake_role_marker": r"^\s*(system|assistant|developer)\s*:",
    "secret_exfiltration": (
        r"\b(reveal|show|print|give|share|leak)\b[^.]{0,30}"
        r"\b(api[ _-]?keys?|secrets?|tokens?|passwords?|credentials?)\b"
    ),
}
_INJECTION_RE = {
    name: re.compile(pattern, re.IGNORECASE | re.MULTILINE)
    for name, pattern in _INJECTION_PATTERNS.items()
}


def detect_injection(text: str) -> list:
    flat = re.sub(r"[ \t]+", " ", text)
    return [name for name, rx in _INJECTION_RE.items() if rx.search(flat)]


_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_SECRET = re.compile(
    r"\b(?:sk-[A-Za-z0-9_-]{16,}|AIza[0-9A-Za-z_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}"
    r"|AKIA[0-9A-Z]{16}|xox[baprs]-[A-Za-z0-9-]{10,})"
)
_NUMBER_RUN = re.compile(r"(?<!\w)\+?\d[\d \-().]{7,}\d(?!\w)")


def _luhn_ok(digits: str) -> bool:
    total, flip = 0, False
    for ch in reversed(digits):
        d = int(ch)
        if flip:
            d *= 2
            if d > 9:
                d -= 9
        total += d
        flip = not flip
    return total % 10 == 0


def mask_pii(text: str):
    """Return (masked_text, set_of_kinds). Dates and short numbers are left alone."""
    kinds = set()

    def _sub(kind, token):
        def repl(_match):
            kinds.add(kind)
            return token

        return repl

    text = _SECRET.sub(_sub("secret", "[SECRET]"), text)
    text = _EMAIL.sub(_sub("email", "[EMAIL]"), text)

    def _numbers(match):
        digits = re.sub(r"\D", "", match.group())
        if 13 <= len(digits) <= 19 and _luhn_ok(digits):
            kinds.add("card")
            return "[CARD]"
        if len(digits) >= 9:
            kinds.add("phone")
            return "[PHONE]"
        return match.group()

    text = _NUMBER_RUN.sub(_numbers, text)
    return text, kinds


def validate_input(text: str, max_length: int = 4000) -> SecurityResult:
    cleaned = normalize(text or "")
    if not cleaned:
        return SecurityResult(BLOCKED, "", ["empty_input"])
    if len(cleaned) > max_length:
        return SecurityResult(BLOCKED, "", ["input_too_long"])
    hits = detect_injection(cleaned)
    if hits:
        return SecurityResult(BLOCKED, "", hits)
    masked, kinds = mask_pii(cleaned)
    if kinds:
        return SecurityResult(MASKED, masked, [f"pii_{k}" for k in sorted(kinds)])
    return SecurityResult(ALLOWED, cleaned, [])


def filter_output(text: str, max_length: int = 3000, canary: Optional[str] = None) -> SecurityResult:
    cleaned = normalize(text or "")
    if canary and canary in cleaned:
        return SecurityResult(BLOCKED, SAFE_OUTPUT_FALLBACK, ["system_prompt_leak"])
    reasons = []
    redacted = _SECRET.sub("[SECRET]", cleaned)
    if redacted != cleaned:
        reasons.append("secret_redacted")
    if len(redacted) > max_length:
        redacted = redacted[:max_length].rstrip() + "..."
        reasons.append("output_truncated")
    if not redacted:
        return SecurityResult(BLOCKED, SAFE_OUTPUT_FALLBACK, ["empty_output"])
    return SecurityResult(MASKED if reasons else ALLOWED, redacted, reasons)


class StreamFilter:

    HOLDBACK = 96

    def __init__(self, max_length: int = 3000, canary: Optional[str] = None):
        self.max_length = max_length
        self.canary = canary
        self.leaked = False
        self._raw = ""
        self._emitted = 0

    def _redacted(self) -> str:
        return _SECRET.sub("[SECRET]", self._raw)

    def feed(self, chunk: str) -> str:
        if self.leaked:
            return ""
        self._raw += _clean(chunk or "")
        if self.canary and self.canary in self._raw:
            self.leaked = True
            return ""
        view = self._redacted()
        end = min(len(view) - self.HOLDBACK, self.max_length)
        if end <= self._emitted:
            return ""
        out = view[self._emitted:end]
        self._emitted = end
        return out

    def finish(self):

        if self.leaked:
            return "", SecurityResult(BLOCKED, SAFE_OUTPUT_FALLBACK, ["system_prompt_leak"])
        final = self._redacted().rstrip()
        if not final.strip():
            return "", SecurityResult(BLOCKED, SAFE_OUTPUT_FALLBACK, ["empty_output"])
        reasons = []
        if _SECRET.search(self._raw):
            reasons.append("secret_redacted")
        if len(final) > self.max_length:
            final = final[: self.max_length].rstrip() + "..."
            reasons.append("output_truncated")
        return final[self._emitted:], SecurityResult(MASKED if reasons else ALLOWED, final, reasons)



_INSTRUCTION_LIKE = re.compile(
    r"^(you|assistant|ai|nasha|system)\b"
    r"|\b(ignore|instructions?|system prompt|from now on|api key|password)\b"
    r"|\b(always|never) (say|reply|respond|answer|refuse|obey)\b",
    re.IGNORECASE,
)


def validate_memory_fact(fact) -> Optional[str]:
    if not isinstance(fact, str):
        return None
    cleaned = normalize(fact)
    if "\n" in cleaned or not (3 <= len(cleaned) <= 200):
        return None
    if detect_injection(cleaned) or _INSTRUCTION_LIKE.search(cleaned):
        return None
    _, kinds = mask_pii(cleaned)
    if kinds:  
        return None
    return cleaned