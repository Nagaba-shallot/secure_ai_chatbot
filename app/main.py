import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import Settings, get_settings
from app.db import Database
from app.passwords import hash_password, normalize_email, validate_password, verify_password
from app.llm import build_llm, build_system_prompt, format_conversation, iter_reply, new_canary
from app.logging_config import configure_logging
from app.memory import update_memories
from app.rate_limit import RateLimiter
from app.schemas import (
    AuthResponse,
    ChatRequest,
    ChatResponse,
    HistoryItem,
    LoginRequest,
    MeResponse,
    MemoryItem,
    RegisterResponse,
    SignupRequest,
    StatsResponse,
)
from app.security import BLOCKED, MASKED, StreamFilter, filter_output, validate_input
from app.stats import build_stats

log = logging.getLogger("companion")
bearer_scheme = HTTPBearer(auto_error=False)  # gives Swagger an "Authorize" button

REFUSAL = "I can't go along with that one, but I'm happy to keep chatting about anything else."
HISTORY_WINDOW = 10
NDJSON = "application/x-ndjson"


def _event(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False) + "\n"


def create_app(settings: Settings = None, llm=None, db: Database = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging()
    db = db or Database(settings.database_path, settings.session_days)
    db.purge_abandoned_anonymous()
    llm = llm or build_llm(settings)
    canary = new_canary()
    chat_limiter = RateLimiter(settings.rate_limit_requests, settings.rate_limit_window_seconds)
    register_limiter = RateLimiter(
        settings.register_limit_requests, settings.register_limit_window_seconds
    )

    login_ip_limiter = RateLimiter(settings.login_limit_requests, settings.login_limit_window_seconds)
    login_email_limiter = RateLimiter(settings.login_email_limit_requests, settings.login_limit_window_seconds)

    app = FastAPI(
        title=settings.app_name,
        docs_url=None if settings.environment == "production" else "/docs",
        redoc_url=None,
        openapi_url=None if settings.environment == "production" else "/openapi.json",
    )

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    def bearer_token(creds: HTTPAuthorizationCredentials = Depends(bearer_scheme)) -> str:
        return creds.credentials.strip() if creds and creds.scheme.lower() == "bearer" else ""

    def optional_user(token: str = Depends(bearer_token)) -> Optional[str]:
        return db.user_id_for_token(token) if token else None

    def current_user(user_id: Optional[str] = Depends(optional_user)) -> str:
        if not user_id:
            raise HTTPException(
                status_code=401,
                detail="Missing or invalid credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return user_id

    def client_ip(request: Request) -> str:
        
        direct = request.client.host if request.client else "unknown"
        hops = settings.trusted_proxy_count
        if hops <= 0:
            return direct
        entries = [e.strip() for e in request.headers.get("x-forwarded-for", "").split(",") if e.strip()]
        return entries[-hops] if len(entries) >= hops else direct

    def guest_limit() -> int:
        return 0 if settings.require_signin else settings.guest_message_limit

    def seconds_until_midnight_utc() -> int:
        now = datetime.now(timezone.utc)
        tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        return max(1, int((tomorrow - now).total_seconds()))

    def gate_model_use(user_id: str) -> None:
        user = db.get_user(user_id)
        if user and user["anonymous"] and db.count_user_messages(user_id) >= guest_limit():
            record(user_id, "rate_limited", "guest")
            raise HTTPException(
                status_code=403,
                detail={"code": "guest_limit", "message": "Create a free account to keep chatting."},
            )
        if not db.consume_daily_call(settings.daily_llm_call_limit):
            record(user_id, "rate_limited", "daily_cap")
            raise HTTPException(
                status_code=503,
                detail={"code": "daily_cap", "message": "Nasha has reached her limit for today. Please come back tomorrow."},
                headers={"Retry-After": str(seconds_until_midnight_utc())},
            )

    def memory_allowed() -> bool:
        return db.consume_daily_call(settings.daily_llm_call_limit)

    admin_ids = {part.strip() for part in settings.admin_user_ids.split(",") if part.strip()}

    def record(user_id, kind, detail=""):
        try:
            db.record_event(user_id, kind, detail)
        except Exception as exc:  # noqa: BLE001
            log.warning("event_log_failed type=%s", type(exc).__name__)

    def log_input_event(user_id, checked):
        attack_reasons = set(checked.reasons) - {"empty_input", "input_too_long"}
        if checked.action == BLOCKED and attack_reasons:
            record(user_id, "input_blocked", ",".join(checked.reasons))
        elif checked.action == MASKED:
            record(user_id, "input_masked", ",".join(checked.reasons))

    def log_output_event(user_id, result):
        if result.action == BLOCKED:
            record(user_id, "output_blocked", ",".join(result.reasons))
        elif "secret_redacted" in result.reasons:
            record(user_id, "output_redacted", "secret_redacted")

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.post("/auth/register", response_model=RegisterResponse, status_code=201)
    def register(request: Request):
        if not settings.registration_open:
            raise HTTPException(status_code=403, detail="Registration is closed")
        ip = request.client.host if request.client else "unknown"
        if not register_limiter.allow(ip):
            record(None, "rate_limited", "signup")
            raise HTTPException(
                status_code=429,
                detail="Too many sign-ups from this address",
                headers={"Retry-After": str(register_limiter.retry_after(ip))},
            )
        user_id, token = db.create_user()
        return RegisterResponse(user_id=user_id, token=token)

    @app.post("/auth/signup", response_model=AuthResponse, status_code=201)
    def signup(body: SignupRequest, request: Request, current: Optional[str] = Depends(optional_user)):
       
        if not settings.registration_open:
            raise HTTPException(status_code=403, detail="Registration is closed")
        ip = client_ip(request)
        if not register_limiter.allow(ip):
            record(None, "rate_limited", "signup")
            raise HTTPException(
                status_code=429,
                detail="Too many sign-ups from this address",
                headers={"Retry-After": str(register_limiter.retry_after(ip))},
            )

        email = normalize_email(body.email)
        if not email:
            raise HTTPException(status_code=400, detail="Enter a valid email address.")
        problem = validate_password(body.password, email)
        if problem:
            raise HTTPException(status_code=400, detail=problem)

        existing = db.get_user(current) if current else None
        if existing and not existing["anonymous"]:
            raise HTTPException(status_code=409, detail="You're already signed in.")

        password_hash = hash_password(body.password)
        taken = HTTPException(status_code=409, detail="An account with this email already exists.")
        if existing:
            if not db.set_credentials(existing["id"], email, password_hash):
                raise taken
            db.revoke_user_sessions(existing["id"])
            user_id = existing["id"]
        else:
            user_id = db.create_account(email, password_hash)
            if not user_id:
                raise taken
        return AuthResponse(user_id=user_id, token=db.create_session(user_id), email=email)

    @app.post("/auth/login", response_model=AuthResponse)
    def login(body: LoginRequest, request: Request):
        ip = client_ip(request)
        if not login_ip_limiter.allow(ip):
            record(None, "rate_limited", "login")
            raise HTTPException(
                status_code=429,
                detail="Too many sign-in attempts. Try again later.",
                headers={"Retry-After": str(login_ip_limiter.retry_after(ip))},
            )
        email = normalize_email(body.email) or ""
        if email and not login_email_limiter.allow(email):
            record(None, "rate_limited", "login")
            raise HTTPException(
                status_code=429,
                detail="Too many sign-in attempts. Try again later.",
                headers={"Retry-After": str(login_email_limiter.retry_after(email))},
            )

        row = db.find_user_by_email(email) if email else None
        valid = verify_password(body.password, row["password_hash"] if row else None)
        if not row or not valid:
            log.warning("login_failed ip=%s", ip)
            record(None, "login_failed")
            raise HTTPException(status_code=401, detail="Incorrect email or password.")

        db.purge_expired_sessions()
        db.purge_old_events(settings.event_retention_days)
        return AuthResponse(user_id=row["id"], token=db.create_session(row["id"]), email=email)

    @app.post("/auth/logout", status_code=204)
    def logout(token: str = Depends(bearer_token), user_id: str = Depends(current_user)):
        db.revoke_session(token)  # only this device; other sessions stay signed in
        return Response(status_code=204)

    @app.get("/auth/me", response_model=MeResponse)
    def me(user_id: str = Depends(current_user)):
        user = db.get_user(user_id)
        left = None
        if user["anonymous"]:
            left = max(0, guest_limit() - db.count_user_messages(user_id))
        return MeResponse(
            user_id=user["id"],
            email=user["email"],
            anonymous=user["anonymous"],
            is_admin=user["id"] in admin_ids,
            guest_messages_left=left,
        )

    @app.post("/chat", response_model=ChatResponse)
    def chat(body: ChatRequest, background: BackgroundTasks, user_id: str = Depends(current_user)):
        request_id = uuid.uuid4().hex

        if not chat_limiter.allow(user_id):
            record(user_id, "rate_limited", "chat")
            raise HTTPException(
                status_code=429,
                detail="Too many messages, give it a minute.",
                headers={"Retry-After": str(chat_limiter.retry_after(user_id))},
            )

        checked = validate_input(body.message, settings.max_input_length)
        log_input_event(user_id, checked)
        if checked.action == BLOCKED:
            log.warning("input_blocked request=%s user=%s reasons=%s", request_id, user_id, checked.reasons)
            if {"empty_input", "input_too_long"} & set(checked.reasons):
                raise HTTPException(status_code=400, detail="Message is empty or too long")
            return ChatResponse(response=REFUSAL, security_action=BLOCKED, request_id=request_id)

        gate_model_use(user_id)
        history = db.recent_messages(user_id, HISTORY_WINDOW)
        memories = [m["fact"] for m in db.list_memories(user_id)]
        try:
            raw_reply = llm.complete(
                build_system_prompt(memories, canary),
                format_conversation(history, checked.text),
            )
        except Exception as exc:  # noqa: BLE001
            log.error("llm_error request=%s type=%s", request_id, type(exc).__name__)
            raise HTTPException(status_code=502, detail="Couldn't get a reply right now, try again.")

        reply = filter_output(raw_reply, settings.max_output_length, canary)
        log_output_event(user_id, reply)
        if reply.action == BLOCKED:
            log.warning("output_blocked request=%s user=%s reasons=%s", request_id, user_id, reply.reasons)

        db.add_message(user_id, "user", checked.text)
        db.add_message(user_id, "assistant", reply.text)

        if db.count_user_messages(user_id) % settings.memory_every_n_messages == 0:
            background.add_task(update_memories, db, llm, user_id, settings.max_memories_per_user, allow=memory_allowed)

        if reply.action == BLOCKED:
            action = "output_blocked"
        elif MASKED in (checked.action, reply.action):
            action = MASKED
        else:
            action = checked.action
        return ChatResponse(response=reply.text, security_action=action, request_id=request_id)

    @app.post("/chat/stream")
    def chat_stream(body: ChatRequest, user_id: str = Depends(current_user)):
     
        request_id = uuid.uuid4().hex

        if not chat_limiter.allow(user_id):
            record(user_id, "rate_limited", "chat")
            raise HTTPException(
                status_code=429,
                detail="Too many messages, give it a minute.",
                headers={"Retry-After": str(chat_limiter.retry_after(user_id))},
            )

        checked = validate_input(body.message, settings.max_input_length)
        log_input_event(user_id, checked)
        if checked.action == BLOCKED:
            log.warning("input_blocked request=%s user=%s reasons=%s", request_id, user_id, checked.reasons)
            if {"empty_input", "input_too_long"} & set(checked.reasons):
                raise HTTPException(status_code=400, detail="Message is empty or too long")
            refusal = [
                _event({"type": "delta", "text": REFUSAL}),
                _event({"type": "done", "security_action": BLOCKED, "request_id": request_id}),
            ]
            return StreamingResponse(iter(refusal), media_type=NDJSON)

        gate_model_use(user_id)
        history = db.recent_messages(user_id, HISTORY_WINDOW)
        memories = [m["fact"] for m in db.list_memories(user_id)]
        system_prompt = build_system_prompt(memories, canary)
        user_input = format_conversation(history, checked.text)

        def generate():
            guard = StreamFilter(settings.max_output_length, canary)
            try:
                for piece in iter_reply(llm, system_prompt, user_input):
                    shown = guard.feed(piece)
                    if guard.leaked:
                        break
                    if shown:
                        yield _event({"type": "delta", "text": shown})
            except Exception as exc:  # noqa: BLE001
                log.error("llm_error request=%s type=%s", request_id, type(exc).__name__)
                yield _event({"type": "error", "detail": "Couldn't get a reply right now, try again."})
                return

            tail, result = guard.finish()
            log_output_event(user_id, result)
            if result.action == BLOCKED:
                log.warning("output_blocked request=%s user=%s reasons=%s", request_id, user_id, result.reasons)
                yield _event({"type": "replace", "text": result.text})
            elif tail:
                yield _event({"type": "delta", "text": tail})

            db.add_message(user_id, "user", checked.text)
            db.add_message(user_id, "assistant", result.text)

            if result.action == BLOCKED:
                action = "output_blocked"
            elif MASKED in (checked.action, result.action):
                action = MASKED
            else:
                action = checked.action
            yield _event({"type": "done", "security_action": action, "request_id": request_id})

            if db.count_user_messages(user_id) % settings.memory_every_n_messages == 0:
                update_memories(db, llm, user_id, settings.max_memories_per_user, allow=memory_allowed)

        return StreamingResponse(generate(), media_type=NDJSON, headers={"X-Accel-Buffering": "no"})

    @app.get("/stats", response_model=StatsResponse)
    def stats(days: int = 14, scope: str = "me", user_id: str = Depends(current_user)):
        days = max(1, min(days, 90))
        if scope not in ("me", "all"):
            raise HTTPException(status_code=400, detail="scope must be 'me' or 'all'")
        owner = user_id
        if scope == "all":
            if user_id not in admin_ids:
                raise HTTPException(status_code=403, detail="Only admins can see everyone's activity")
            owner = None
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec="seconds")
        result = build_stats(db.event_rows(since, owner), days)
        result["scope"] = scope
        result["recent"] = db.recent_events(20, owner)
        return result

    @app.get("/history", response_model=list[HistoryItem])
    def history(limit: int = 50, user_id: str = Depends(current_user)):
        return db.recent_messages(user_id, max(1, min(limit, 100)))

    @app.get("/memories", response_model=list[MemoryItem])
    def list_memories(user_id: str = Depends(current_user)):
        return db.list_memories(user_id)

    @app.delete("/memories/{memory_id}", status_code=204)
    def delete_memory(memory_id: int, user_id: str = Depends(current_user)):
        if not db.delete_memory(user_id, memory_id):
            raise HTTPException(status_code=404, detail="Memory not found")
        return Response(status_code=204)

    @app.delete("/me", status_code=204)
    def delete_account(user_id: str = Depends(current_user)):
        db.delete_user(user_id)  # cascades to messages and memories
        return Response(status_code=204)

    return app


def get_app() -> FastAPI:
    return create_app()