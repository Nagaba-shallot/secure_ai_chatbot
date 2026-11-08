import base64
import hashlib
import hmac
import os
import re
from typing import Optional

_N, _R, _P, _DKLEN = 2**14, 8, 1, 32
_MAX_MEM = 64 * 1024 * 1024

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_COMMON = {"1234567890", "0123456789", "qwertyuiop", "password12", "password123", "password1234", "1111111111"}

MIN_LENGTH = 10
MAX_LENGTH = 128  


def _b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=_N, r=_R, p=_P, dklen=_DKLEN, maxmem=_MAX_MEM)
    return f"scrypt${_N}${_R}${_P}${_b64(salt)}${_b64(digest)}"


_dummy_hash = None


def _dummy() -> str:
    global _dummy_hash
    if _dummy_hash is None:
        _dummy_hash = hash_password("not-a-real-password")
    return _dummy_hash


def verify_password(password: str, stored: Optional[str]) -> bool:
    """Constant-effort check. With no stored hash it still does the work, so an unknown
    email takes about as long as a wrong password and the two can't be told apart by timing."""
    known = bool(stored)
    try:
        scheme, n, r, p, salt, expected = (stored or _dummy()).split("$")
        if scheme != "scrypt":
            return False
        digest = hashlib.scrypt(
            password.encode("utf-8"),
            salt=base64.b64decode(salt),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=_DKLEN,
            maxmem=_MAX_MEM,
        )
        matches = hmac.compare_digest(digest, base64.b64decode(expected))
    except (ValueError, TypeError):
        return False
    return matches and known


def normalize_email(email: str) -> Optional[str]:
    cleaned = (email or "").strip().lower()
    if len(cleaned) > 254 or not _EMAIL.match(cleaned):
        return None
    return cleaned


def validate_password(password: str, email: str = "") -> Optional[str]:
    """Return a message the user can act on, or None if the password is acceptable."""
    if len(password) < MIN_LENGTH:
        return f"Use at least {MIN_LENGTH} characters."
    if len(password) > MAX_LENGTH:
        return f"Use at most {MAX_LENGTH} characters."
    if password.lower() == email or password.lower() in _COMMON:
        return "That password is too easy to guess. Try a longer phrase."
    return None