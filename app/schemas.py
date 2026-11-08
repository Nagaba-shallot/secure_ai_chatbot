from typing import Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)


class ChatResponse(BaseModel):
    response: str
    security_action: str  # allowed | masked | blocked | output_blocked
    request_id: str


class RegisterResponse(BaseModel):
    user_id: str
    token: str


class MemoryItem(BaseModel):
    id: int
    fact: str
    created_at: str


class HistoryItem(BaseModel):
    role: str
    content: str


class SignupRequest(BaseModel):
    email: str = Field(..., max_length=254)
    password: str = Field(..., max_length=1000)  # the real limits are enforced (with clear messages) in code


class LoginRequest(BaseModel):
    email: str = Field(..., max_length=254)
    password: str = Field(..., max_length=1000)


class AuthResponse(BaseModel):
    user_id: str
    token: str
    email: Optional[str] = None


class MeResponse(BaseModel):
    user_id: str
    email: Optional[str] = None
    anonymous: bool
    is_admin: bool = False
    guest_messages_left: Optional[int] = None  # None once signed in


class StatsResponse(BaseModel):
    days: int
    scope: str
    totals: dict[str, int]
    daily: list[dict]
    rules: list[dict]
    recent: list[dict]