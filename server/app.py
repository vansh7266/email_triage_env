import asyncio
import base64
import hashlib
import json
import logging
import os
import re
import secrets
import sys
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlencode

from cryptography.fernet import Fernet, InvalidToken
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

from server.email_triage_env_environment import EmailTriageEnvEnvironment

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("triageai")

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
STATIC_DIR = FRONTEND_DIR / "static"
ASSET_VERSION = os.getenv("ASSET_VERSION", "20260506b")

SESSION_COOKIE_NAME = "token_data"
OAUTH_STATE_COOKIE = "oauth_state"
OAUTH_VERIFIER_COOKIE = "oauth_verifier"
SESSION_MAX_AGE = 3600
OAUTH_MAX_AGE = 600
TRIAGE_BATCH_SIZE = 10
TRIAGE_CONCURRENCY = max(
    1,
    min(TRIAGE_BATCH_SIZE, int(os.getenv("TRIAGE_CONCURRENCY", "8"))),
)

VALID_PRIORITIES = {"low", "medium", "high"}
VALID_DEPARTMENTS = {
    "finance",
    "engineering",
    "customer_success",
    "sales",
    "security",
    "marketing",
}

PRIORITY_ALIASES = {
    "low": "low",
    "medium": "medium",
    "med": "medium",
    "normal": "medium",
    "moderate": "medium",
    "high": "high",
    "urgent": "high",
    "critical": "high",
    "immediate": "high",
}

DEPARTMENT_ALIASES = {
    "finance": "finance",
    "billing": "finance",
    "accounts": "finance",
    "payments": "finance",
    "engineering": "engineering",
    "technical": "engineering",
    "tech": "engineering",
    "support": "customer_success",
    "customer support": "customer_success",
    "customer success": "customer_success",
    "success": "customer_success",
    "sales": "sales",
    "account manager": "sales",
    "growth": "marketing",
    "marketing": "marketing",
    "campaign": "marketing",
    "security": "security",
    "fraud": "security",
    "trust": "security",
}

DEPARTMENT_KEYWORDS = {
    "security": {
        "breach",
        "phishing",
        "security",
        "unauthorized",
        "fraud",
        "lawyer",
        "legal",
        "gdpr",
        "leak",
        "risk",
        "blocked card",
        "incident",
    },
    "finance": {
        "invoice",
        "refund",
        "charge",
        "charged",
        "billing",
        "payment",
        "subscription",
        "pricing",
        "double billed",
        "credit note",
    },
    "engineering": {
        "bug",
        "error",
        "login",
        "cannot log in",
        "api",
        "integration",
        "rate limit",
        "outage",
        "down",
        "crash",
        "feature request",
        "403",
        "500",
    },
    "sales": {
        "quote",
        "plan",
        "enterprise",
        "upgrade",
        "demo",
        "pricing inquiry",
        "proposal",
        "contract",
    },
    "marketing": {
        "newsletter",
        "campaign",
        "webinar",
        "press",
        "media",
        "partnership",
        "sponsorship",
    },
    "customer_success": {
        "complaint",
        "cancel",
        "not happy",
        "support",
        "switching",
        "disappointed",
        "help",
        "follow up",
        "response",
        "customer",
    },
}

HIGH_PRIORITY_TERMS = {
    "urgent",
    "asap",
    "immediately",
    "critical",
    "outage",
    "down",
    "blocked",
    "data breach",
    "security incident",
    "lawyer",
    "refund immediately",
    "production",
    "cannot log in",
    "rate limit",
    "losing customers",
}
LOW_PRIORITY_TERMS = {
    "newsletter",
    "promotion",
    "webinar",
    "hello",
    "question",
    "curious",
    "suggestion",
}
ESCALATION_TERMS = {
    "breach",
    "legal",
    "lawyer",
    "lawsuit",
    "fraud",
    "unauthorized",
    "critical churn",
    "switching to your competitor",
    "ceo-level",
    "security incident",
    "engage our lawyers",
}

TOPIC_DEFAULTS = {
    "finance": "Billing Issue",
    "engineering": "Technical Issue",
    "customer_success": "Support Request",
    "sales": "Sales Inquiry",
    "security": "Security Alert",
    "marketing": "Marketing Request",
}

limiter = Limiter(key_func=get_remote_address)


SECRET_KEY = os.getenv("SECRET_KEY", "").strip()
if not SECRET_KEY or SECRET_KEY == "YOUR_SECRET_KEY_HERE":
    logger.warning(
        "SECRET_KEY is not set or is using the placeholder. "
        "Generating a temporary key for this process."
    )
    SECRET_KEY = secrets.token_urlsafe(32)


def _build_cookie_cipher() -> Fernet:
    configured_key = os.getenv("COOKIE_ENCRYPTION_KEY", "").strip()
    if configured_key:
        try:
            return Fernet(configured_key.encode("utf-8"))
        except Exception:
            logger.warning(
                "COOKIE_ENCRYPTION_KEY is invalid. Falling back to a derived key."
            )

    derived_key = base64.urlsafe_b64encode(
        hashlib.sha256(SECRET_KEY.encode("utf-8")).digest()
    )
    return Fernet(derived_key)


token_cipher = _build_cookie_cipher()


def encrypt_token(data: dict) -> str:
    payload = json.dumps(data, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return token_cipher.encrypt(payload).decode("utf-8")


def decrypt_token(encrypted_data: str, max_age: int = SESSION_MAX_AGE) -> dict:
    try:
        decrypted = token_cipher.decrypt(
            encrypted_data.encode("utf-8"),
            ttl=max_age,
        )
        return json.loads(decrypted.decode("utf-8"))
    except (InvalidToken, json.JSONDecodeError) as exc:
        raise ValueError("Invalid or expired session token.") from exc


def _set_cookie(response: Response, key: str, value: str, max_age: int) -> None:
    response.set_cookie(
        key=key,
        value=value,
        httponly=True,
        secure=IS_PRODUCTION,
        samesite="lax",
        max_age=max_age,
        path="/",
    )


def _clear_auth_cookies(response: Response) -> None:
    for cookie_name in (
        SESSION_COOKIE_NAME,
        OAUTH_STATE_COOKIE,
        OAUTH_VERIFIER_COOKIE,
    ):
        response.delete_cookie(cookie_name, path="/")


def _read_frontend_file(filename: str) -> str:
    content = (FRONTEND_DIR / filename).read_text(encoding="utf-8")
    return content.replace("__ASSET_VERSION__", ASSET_VERSION)


def _cacheless_json(payload: dict, status_code: int = 200) -> JSONResponse:
    return JSONResponse(
        payload,
        status_code=status_code,
        headers={"Cache-Control": "no-store"},
    )


def _cacheless_html(content: str) -> HTMLResponse:
    return HTMLResponse(content=content, headers={"Cache-Control": "no-store"})


def _landing_error_redirect(message: str, detail: str | None = None) -> RedirectResponse:
    query = {"auth_error": message}
    if detail:
        query["auth_detail"] = detail[:180]
    response = RedirectResponse(url=f"/?{urlencode(query)}", status_code=303)
    response.headers["Cache-Control"] = "no-store"
    _clear_auth_cookies(response)
    return response


def _get_session_data(request: Request) -> dict:
    cookie = request.cookies.get(SESSION_COOKIE_NAME)
    if not cookie:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        return decrypt_token(cookie)
    except ValueError:
        raise HTTPException(status_code=401, detail="Session expired. Please login again.")


def _is_authenticated(request: Request) -> bool:
    cookie = request.cookies.get(SESSION_COOKIE_NAME)
    if not cookie:
        return False
    try:
        decrypt_token(cookie)
        return True
    except ValueError:
        return False


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=()"
        )
        if IS_PRODUCTION:
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
            response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self'; "
                "style-src 'self' https://fonts.googleapis.com; "
                "font-src 'self' https://fonts.gstatic.com; "
                "img-src 'self' data:; "
                "connect-src 'self'; "
                "object-src 'none'; "
                "base-uri 'self'; "
                "form-action 'self'; "
                "frame-ancestors 'none';"
            )
            response.headers["Strict-Transport-Security"] = (
                "max-age=63072000; includeSubDomains; preload"
            )
        else:
            response.headers["Cross-Origin-Resource-Policy"] = "cross-origin"
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self'; "
                "style-src 'self' https://fonts.googleapis.com; "
                "font-src 'self' https://fonts.gstatic.com; "
                "img-src 'self' data:; "
                "connect-src 'self'; "
                "object-src 'none'; "
                "base-uri 'self'; "
                "form-action 'self';"
            )
        return response


REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/callback")
IS_PRODUCTION = "localhost" not in REDIRECT_URI and "127.0.0.1" not in REDIRECT_URI

ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:8000,https://vansh7266-email-triage-env.hf.space",
).split(",")

app = FastAPI(
    title="Email Triage RL Environment",
    description=(
        "An OpenEnv-compatible reinforcement learning environment "
        "for training AI agents to triage and route emails. "
        "Built for the Meta x PyTorch OpenEnv Hackathon 2026."
    ),
    version="1.0.0",
    docs_url="/docs" if not IS_PRODUCTION else None,
    redoc_url="/redoc" if not IS_PRODUCTION else None,
)

app.state.limiter = limiter
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)

env = EmailTriageEnvEnvironment()


class ResetRequest(BaseModel):
    task_id: Optional[int] = None


class ResetResponse(BaseModel):
    observation: Dict[str, Any]


class TriageRequest(BaseModel):
    page_token: Optional[str] = None


class StepRequest(BaseModel):
    action: Dict[str, Any]


class StepResponse(BaseModel):
    observation: Dict[str, Any]
    reward: Dict[str, Any]
    done: bool
    info: Dict[str, Any]


class StateResponse(BaseModel):
    state: Dict[str, Any]


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return _cacheless_json(
        {"detail": "Rate limit exceeded. Please try again later."},
        status_code=429,
    )


@app.post("/reset", response_model=ResetResponse)
def reset(request: ResetRequest = None):
    try:
        task_id = request.task_id if request else None
        result = env.reset(task_id=task_id)
        return ResetResponse(observation=result["observation"])
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/step", response_model=StepResponse)
def step(request: StepRequest):
    try:
        result = env.step(request.action)
        return StepResponse(
            observation=result["observation"],
            reward=result["reward"],
            done=result["done"],
            info=result["info"],
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/state", response_model=StateResponse)
def state():
    try:
        result = env.state()
        return StateResponse(state=result)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/health")
def health():
    return {"status": "healthy", "environment": "email_triage_env"}


@app.get("/", response_class=HTMLResponse)
def landing(request: Request):
    if _is_authenticated(request):
        return RedirectResponse(url="/dashboard", status_code=303)
    return _cacheless_html(_read_frontend_file("index.html"))


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard_page(request: Request):
    if not _is_authenticated(request):
        return RedirectResponse(url="/", status_code=303)
    return _cacheless_html(_read_frontend_file("dashboard.html"))


@app.get("/auth/login")
@limiter.limit("10/minute")
def auth_login(request: Request):
    from server.gmail_service import get_auth_url

    try:
        url, state, verifier = get_auth_url()
    except Exception as exc:
        logger.exception("Unable to start OAuth login flow")
        return _landing_error_redirect(
            "Google connection could not start.",
            str(exc),
        )

    response = RedirectResponse(url, status_code=303)
    response.headers["Cache-Control"] = "no-store"
    _set_cookie(response, OAUTH_STATE_COOKIE, state, OAUTH_MAX_AGE)
    if verifier:
        _set_cookie(response, OAUTH_VERIFIER_COOKIE, verifier, OAUTH_MAX_AGE)
    return response


@app.get("/auth/callback")
@limiter.limit("10/minute")
def auth_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
):
    if error:
        return _landing_error_redirect(
            "Google sign-in was not completed.",
            error_description or error.replace("_", " "),
        )

    oauth_state = request.cookies.get(OAUTH_STATE_COOKIE)
    oauth_verifier = request.cookies.get(OAUTH_VERIFIER_COOKIE, "")

    if not code or not state:
        return _landing_error_redirect(
            "Google sign-in response was incomplete.",
            "Missing authorization code or state.",
        )

    if not oauth_state or state != oauth_state:
        return _landing_error_redirect(
            "Google sign-in session expired.",
            "Invalid OAuth state. Please try again.",
        )

    from server.gmail_service import exchange_code, fetch_user_profile

    try:
        token_data = exchange_code(code, state, oauth_verifier)
        profile = fetch_user_profile(token_data)
    except Exception as exc:
        logger.exception("OAuth callback failed")
        return _landing_error_redirect(
            "Google connection could not be completed.",
            str(exc),
        )

    allowed_session_fields = {
        "token": token_data.get("token", ""),
        "refresh_token": token_data.get("refresh_token"),
        "token_uri": token_data.get("token_uri", "https://oauth2.googleapis.com/token"),
        "scopes": token_data.get("scopes", []),
    }
    session_payload = {
        **allowed_session_fields,
        "user_email": profile.get("email", ""),
        "user_name": profile.get("name", ""),
    }

    response = RedirectResponse(url="/dashboard", status_code=303)
    response.headers["Cache-Control"] = "no-store"
    _clear_auth_cookies(response)
    _set_cookie(
        response,
        SESSION_COOKIE_NAME,
        encrypt_token(session_payload),
        SESSION_MAX_AGE,
    )
    return response


@app.get("/auth/me")
def auth_me(request: Request):
    session_data = _get_session_data(request)
    return _cacheless_json(
        {
            "email": session_data.get("user_email") or "Connected",
            "name": session_data.get("user_name") or "",
        }
    )


@app.get("/auth/logout")
@app.post("/auth/logout")
def auth_logout():
    response = RedirectResponse(url="/", status_code=303)
    response.headers["Cache-Control"] = "no-store"
    _clear_auth_cookies(response)
    return response


def _clean_model_text(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def _coerce_bool(value: Any) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    normalized = _clean_model_text(value).lower()
    if normalized in {"true", "yes", "y", "1"}:
        return True
    if normalized in {"false", "no", "n", "0"}:
        return False
    return None


def _guess_department(text: str) -> str:
    lowered = text.lower()
    scored_departments: list[tuple[str, int]] = []
    for department, keywords in DEPARTMENT_KEYWORDS.items():
        score = sum(1 for keyword in keywords if keyword in lowered)
        scored_departments.append((department, score))
    department, score = max(scored_departments, key=lambda item: item[1])
    return department if score > 0 else "customer_success"


def _guess_priority(text: str) -> str:
    lowered = text.lower()
    if any(keyword in lowered for keyword in HIGH_PRIORITY_TERMS):
        return "high"
    if any(keyword in lowered for keyword in LOW_PRIORITY_TERMS):
        return "low"
    return "medium"


def _should_escalate(text: str, priority: str, department: str) -> bool:
    lowered = text.lower()
    if any(keyword in lowered for keyword in ESCALATION_TERMS):
        return True
    if department == "security" and priority == "high":
        return True
    return "immediate attention" in lowered or "ceo" in lowered


def _guess_topic(text: str, department: str) -> str:
    lowered = text.lower()
    if department == "finance":
        if "refund" in lowered:
            return "Refund Request"
        if "pricing" in lowered or "quote" in lowered:
            return "Pricing Inquiry"
        return "Billing Issue"
    if department == "engineering":
        if "feature request" in lowered:
            return "Feature Request"
        if "login" in lowered:
            return "Login Issue"
        if "api" in lowered:
            return "API Issue"
        return "Technical Issue"
    if department == "security":
        return "Security Alert"
    if department == "sales":
        return "Sales Inquiry"
    if department == "marketing":
        return "Marketing Request"
    if "cancel" in lowered or "switching" in lowered:
        return "Churn Risk"
    if "complaint" in lowered or "disappointed" in lowered:
        return "Customer Concern"
    return TOPIC_DEFAULTS[department]


def _build_reasoning(action: dict) -> str:
    department_label = action["department"].replace("_", " ")
    if action["escalate"]:
        return (
            f"Routed to {department_label} because the message indicates "
            f"{action['topic'].lower()} with {action['priority']} urgency and needs review."
        )
    return (
        f"Routed to {department_label} because the message indicates "
        f"{action['topic'].lower()} with {action['priority']} urgency."
    )


def _fallback_triage(email: dict) -> dict:
    combined_text = " ".join(
        filter(
            None,
            [
                email.get("subject", ""),
                email.get("body", ""),
                email.get("preview", ""),
                email.get("sender", ""),
            ],
        )
    )
    department = _guess_department(combined_text)
    priority = _guess_priority(combined_text)
    escalate = _should_escalate(combined_text, priority, department)
    topic = _guess_topic(combined_text, department)
    action = {
        "topic": topic,
        "priority": priority,
        "department": department,
        "escalate": escalate,
    }
    action["reasoning"] = _build_reasoning(action)
    return action


def _normalize_priority(value: Any, text: str) -> str:
    cleaned = _clean_model_text(value).lower().replace("-", " ")
    slug = cleaned.replace(" ", "_")
    if cleaned in PRIORITY_ALIASES:
        return PRIORITY_ALIASES[cleaned]
    if slug in PRIORITY_ALIASES:
        return PRIORITY_ALIASES[slug]
    return _guess_priority(text)


def _normalize_department(value: Any, text: str) -> str:
    cleaned = _clean_model_text(value).lower()
    normalized = cleaned.replace("_", " ").replace("-", " ").replace("&", " and ")
    guessed = _guess_department(text)
    if cleaned in VALID_DEPARTMENTS:
        return cleaned
    underscored = normalized.replace(" ", "_")
    if underscored in VALID_DEPARTMENTS:
        return underscored
    for alias, target in DEPARTMENT_ALIASES.items():
        if alias in normalized:
            if target == "customer_success" and guessed != "customer_success":
                return guessed
            return target
    return guessed


def _normalize_topic(value: Any, text: str, department: str) -> str:
    cleaned = _clean_model_text(value).replace("’", "").replace("'", "")
    cleaned = re.sub(r"[^A-Za-z0-9/&+\- ]+", " ", cleaned)
    words = [word for word in cleaned.split() if word]
    topic = " ".join(words[:3]).strip().title()
    generic_topics = {"General", "Inquiry", "Email", "Support"}
    if not topic or topic in generic_topics:
        return _guess_topic(text, department)
    return topic


def _normalize_reasoning(value: Any, action: dict) -> str:
    cleaned = _clean_model_text(value).strip("\"' ")
    if len(cleaned) < 18:
        return _build_reasoning(action)
    if len(cleaned) > 190:
        return f"{cleaned[:189].rstrip()}…"
    return cleaned


def _normalize_action(email: dict, action: dict, fallback: dict) -> dict:
    combined_text = " ".join(
        filter(
            None,
            [
                email.get("subject", ""),
                email.get("body", ""),
                email.get("preview", ""),
                email.get("sender", ""),
                action.get("topic", ""),
                action.get("reasoning", ""),
            ],
        )
    )

    department = _normalize_department(action.get("department"), combined_text)
    priority = _normalize_priority(action.get("priority"), combined_text)
    escalate = _coerce_bool(action.get("escalate"))
    if escalate is None:
        escalate = _should_escalate(combined_text, priority, department)

    normalized = {
        "topic": _normalize_topic(
            action.get("topic") or action.get("category"),
            combined_text,
            department,
        ),
        "priority": priority,
        "department": department,
        "escalate": escalate,
    }
    normalized["reasoning"] = _normalize_reasoning(action.get("reasoning"), normalized)

    if not normalized["topic"]:
        normalized["topic"] = fallback["topic"]
    if normalized["department"] not in VALID_DEPARTMENTS:
        normalized["department"] = fallback["department"]
    if normalized["priority"] not in VALID_PRIORITIES:
        normalized["priority"] = fallback["priority"]
    return normalized


def _parse_llm_json(response_text: str) -> dict:
    text = _clean_model_text(response_text)
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 3:
            text = "\n".join(lines[1:-1]).strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        text = match.group(0)
    return json.loads(text)


def _compute_confidence(action: dict, used_fallback: bool = False) -> float:
    score = 0.46 if used_fallback else 0.64
    if action.get("topic"):
        score += 0.08
    if action.get("priority") in VALID_PRIORITIES:
        score += 0.08
    if action.get("department") in VALID_DEPARTMENTS:
        score += 0.08
    reasoning = action.get("reasoning", "")
    if 24 <= len(reasoning) <= 190:
        score += 0.05
    if action.get("priority") == "high":
        score += 0.03
    if action.get("escalate"):
        score += 0.04
    if action.get("priority") == "high" and action.get("department") == "security":
        score += 0.03
    ceiling = 0.62 if used_fallback else 0.96
    return min(score, ceiling)


def _build_triage_prompt(email: dict) -> str:
    return f"""You are an enterprise email triage agent.
Analyze the email and respond with ONLY valid JSON.

Rules:
- topic must be a concise 1-3 word label
- priority must be one of: low, medium, high
- department must be one of: finance, engineering, customer_success, sales, security, marketing
- escalate must be true or false
- reasoning must be one sentence

Subject: {email['subject']}
From: {email['sender']}
Preview: {email.get('preview', '')}
Body: {email['body'][:700]}

Required JSON:
{{"topic":"1-3 word topic","priority":"low|medium|high","department":"finance|engineering|customer_success|sales|security|marketing","escalate":true,"reasoning":"one sentence"}}"""


@app.post("/triage")
@limiter.limit("20/minute")
async def triage(request: Request, payload: Optional[TriageRequest] = None):
    session_data = _get_session_data(request)
    page_token = payload.page_token if payload else None

    from server.gmail_service import fetch_emails

    try:
        emails, next_page_token = await asyncio.to_thread(
            fetch_emails,
            session_data,
            TRIAGE_BATCH_SIZE,
            page_token,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to fetch Gmail messages")
        raise HTTPException(status_code=500, detail=str(exc))

    if not emails:
        return _cacheless_json(
            {"results": [], "total": 0, "next_page_token": next_page_token}
        )

    from openai import AsyncOpenAI

    client_llm = AsyncOpenAI(
        base_url=os.getenv("API_BASE_URL", "https://router.huggingface.co/v1"),
        api_key=os.getenv("HF_TOKEN", ""),
    )
    semaphore = asyncio.Semaphore(TRIAGE_CONCURRENCY)

    async def process_email(email: dict) -> dict:
        fallback = _fallback_triage(email)
        used_fallback = False

        try:
            async with semaphore:
                completion = await client_llm.chat.completions.create(
                    model=os.getenv("MODEL_NAME", "meta-llama/Llama-3.1-8B-Instruct"),
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are an email triage assistant. "
                                "Return valid JSON only."
                            ),
                        },
                        {"role": "user", "content": _build_triage_prompt(email)},
                    ],
                    temperature=0.1,
                    max_tokens=220,
                )
            raw_action = _parse_llm_json(completion.choices[0].message.content)
        except Exception as exc:
            used_fallback = True
            logger.warning(
                "LLM triage failed for %s: %s",
                email.get("email_id", "unknown"),
                exc,
            )
            raw_action = fallback

        normalized = _normalize_action(email, raw_action, fallback)
        confidence = _compute_confidence(normalized, used_fallback=used_fallback)

        return {
            "email_id": email["email_id"],
            "sender": email["sender"],
            "sender_name": email.get("sender_name", ""),
            "sender_email": email.get("sender_email", ""),
            "subject": email["subject"],
            "preview": email.get("preview") or email["body"][:220],
            "body": email["body"][:700],
            "received_at": email.get("received_at"),
            "topic": normalized["topic"],
            "priority": normalized["priority"],
            "department": normalized["department"],
            "escalate": normalized["escalate"],
            "reasoning": normalized["reasoning"],
            "score": round(confidence, 2),
            "source": "heuristic" if used_fallback else "model",
        }

    results = await asyncio.gather(*(process_email(email) for email in emails))
    return _cacheless_json(
        {
            "results": results,
            "total": len(results),
            "next_page_token": next_page_token,
        }
    )


def main():
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(
        "server.app:app",
        host="0.0.0.0",
        port=port,
        workers=1,
    )


if __name__ == "__main__":
    main()
