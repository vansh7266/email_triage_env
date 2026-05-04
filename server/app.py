from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
import sys
import os
import json
import logging

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import BaseModel
from typing import Any, Dict, Optional
from models import EmailObservation, EmailAction, EmailReward
from server.email_triage_env_environment import EmailTriageEnvEnvironment

# ── Rate Limiting ──────────────────────────────────────────
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)

logger = logging.getLogger("triageai")

# ── SECRET KEY VALIDATION ──────────────────────────────────
SECRET_KEY = os.getenv("SECRET_KEY", "")
if not SECRET_KEY or SECRET_KEY == "YOUR_SECRET_KEY_HERE":
    logger.warning(
        "⚠️  SECRET_KEY is not set or is using the placeholder. "
        "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
    )
    # Use a random key for this session (cookies won't survive restarts)
    import secrets
    SECRET_KEY = secrets.token_urlsafe(32)

# ── Token Encryption ──────────────────────────────────────
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

token_serializer = URLSafeTimedSerializer(SECRET_KEY)

def encrypt_token(data: dict) -> str:
    """Sign and serialize token data for secure cookie storage."""
    return token_serializer.dumps(data)

def decrypt_token(signed_data: str, max_age: int = 3600) -> dict:
    """Verify signature and deserialize token data from cookie."""
    return token_serializer.loads(signed_data, max_age=max_age)

# ── Security Headers Middleware ────────────────────────────
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        # CSP: allow Google Fonts + inline scripts (needed for dashboard)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data:; "
            "connect-src 'self'; "
            "frame-ancestors 'none';"
        )
        return response

# ── Detect Environment ─────────────────────────────────────
REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/callback")
IS_PRODUCTION = "localhost" not in REDIRECT_URI and "127.0.0.1" not in REDIRECT_URI

# ── CORS Origins ───────────────────────────────────────────
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:8000,https://vansh7266-email-triage-env.hf.space"
).split(",")

# ── FastAPI App ────────────────────────────────────────────
app = FastAPI(
    title="Email Triage RL Environment",
    description=(
        "An OpenEnv-compatible reinforcement learning environment "
        "for training AI agents to triage and route emails. "
        "Built for the Meta x PyTorch OpenEnv Hackathon 2026."
    ),
    version="1.0.0",
    # Hide docs in production for security
    docs_url="/docs" if not IS_PRODUCTION else None,
    redoc_url="/redoc" if not IS_PRODUCTION else None,
)

# Add rate limiter to app state
app.state.limiter = limiter

# Custom rate limit error handler
@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return Response(
        content=json.dumps({"detail": "Rate limit exceeded. Please try again later."}),
        status_code=429,
        media_type="application/json",
    )

# Mount static files
app.mount("/static", StaticFiles(directory="frontend/static"), name="static")

# Security headers middleware
app.add_middleware(SecurityHeadersMiddleware)

# CORS — restricted to known origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)

# ── RL Environment ─────────────────────────────────────────
env = EmailTriageEnvEnvironment()

# ── Request/Response Models ────────────────────────────────
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


# ── RL Endpoints ───────────────────────────────────────────

@app.post("/reset", response_model=ResetResponse)
def reset(request: ResetRequest = None):
    try:
        task_id = request.task_id if request else None
        result = env.reset(task_id=task_id)
        return ResetResponse(observation=result["observation"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/state", response_model=StateResponse)
def state():
    try:
        result = env.state()
        return StateResponse(state=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health():
    return {"status": "healthy", "environment": "email_triage_env"}


# ── Web Interface Endpoints ────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def landing():
    with open("frontend/index.html") as f:
        return f.read()

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard_page():
    with open("frontend/dashboard.html") as f:
        return f.read()


# ── Auth Endpoints ─────────────────────────────────────────

@app.get("/auth/login")
@limiter.limit("10/minute")
def auth_login(request: Request):
    from server.gmail_service import get_auth_url
    url, state, verifier = get_auth_url()
    response = RedirectResponse(url)
    response.set_cookie("oauth_state", state, httponly=True, max_age=600, secure=IS_PRODUCTION, samesite="lax")
    if verifier:
        response.set_cookie("oauth_verifier", verifier, httponly=True, max_age=600, secure=IS_PRODUCTION, samesite="lax")
    return response

@app.get("/auth/callback")
@limiter.limit("10/minute")
def auth_callback(code: str, state: str, request: Request):
    oauth_state = request.cookies.get("oauth_state")
    oauth_verifier = request.cookies.get("oauth_verifier", "")

    if not oauth_state or state != oauth_state:
        raise HTTPException(status_code=400, detail="Invalid OAuth state. Please try logging in again.")

    from server.gmail_service import exchange_code
    token_data = exchange_code(code, state, oauth_verifier)

    # Encrypt token data before storing in cookie
    encrypted = encrypt_token(token_data)

    response = RedirectResponse(url="/dashboard")
    response.set_cookie(
        key="token_data",
        value=encrypted,
        httponly=True,
        secure=IS_PRODUCTION,       # HTTPS-only in production
        samesite="lax",             # CSRF protection
        max_age=3600,               # 1 hour expiry
        path="/",
    )
    return response

@app.get("/auth/me")
def auth_me(request: Request):
    cookie = request.cookies.get("token_data")
    if not cookie:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        td = decrypt_token(cookie)
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        creds = Credentials(
            token=td["token"],
            refresh_token=td.get("refresh_token"),
            token_uri=td["token_uri"],
            client_id=td["client_id"],
            client_secret=td["client_secret"],
        )
        service = build("oauth2", "v2", credentials=creds)
        info = service.userinfo().get().execute()
        return {"email": info.get("email"), "name": info.get("name")}
    except (BadSignature, SignatureExpired):
        raise HTTPException(status_code=401, detail="Session expired. Please login again.")
    except Exception:
        return {"email": "Connected"}

@app.get("/auth/logout")
def auth_logout():
    """Clear auth cookie and redirect to landing page."""
    response = RedirectResponse(url="/")
    response.delete_cookie("token_data", path="/")
    return response


# ── Triage Endpoint ────────────────────────────────────────

def _compute_confidence(action: dict) -> float:
    """
    Compute a heuristic confidence score for LLM triage results.
    """
    score = 0.80  # Base confidence

    valid_priorities = {"low", "medium", "high"}
    valid_departments = {"finance", "engineering", "customer_success", "sales", "security", "marketing"}

    # Boost for valid enum values
    if action.get("topic"):
        score += 0.04
    if action.get("priority") in valid_priorities:
        score += 0.04
    if action.get("department") in valid_departments:
        score += 0.04

    # Boost for having reasoning
    reasoning = action.get("reasoning", "")
    if reasoning and len(reasoning) > 10:
        score += 0.03

    # High priority + escalate = confident urgent detection
    if action.get("priority") == "high" and action.get("escalate"):
        score += 0.02

    return min(score, 0.99)  # Cap at 0.99


@app.post("/triage")
@limiter.limit("20/minute")
async def triage(request: Request, payload: Optional[TriageRequest] = None):
    cookie = request.cookies.get("token_data")
    if not cookie:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        td = decrypt_token(cookie)
    except (BadSignature, SignatureExpired):
        raise HTTPException(status_code=401, detail="Session expired. Please login again.")

    try:
        page_token = payload.page_token if payload else None
        from server.gmail_service import fetch_emails
        emails, next_page_token = fetch_emails(td, max_results=10, page_token=page_token)

        if not emails:
            return {"results": [], "total": 0, "next_page_token": next_page_token}

        # Create LLM client ONCE
        from openai import AsyncOpenAI
        client_llm = AsyncOpenAI(
            base_url=os.getenv("API_BASE_URL", "https://router.huggingface.co/v1"),
            api_key=os.getenv("HF_TOKEN", ""),
        )

        async def process_email(email):
            prompt = f"""You are an email triage agent. Analyze this email and respond with ONLY valid JSON.

Subject: {email['subject']}
From: {email['sender']}
Body: {email['body'][:500]}

Required JSON:
{{"topic": "1-3 word dynamic category describing the email (e.g. Feature Request, Newsletter, Job Inquiry, Bug Report)",
  "priority": "low|medium|high",
  "department": "finance|engineering|customer_success|sales|security|marketing",
  "escalate": true or false,
  "reasoning": "one sentence"}}"""

            try:
                completion = await client_llm.chat.completions.create(
                    model=os.getenv("MODEL_NAME", "meta-llama/Llama-3.1-8B-Instruct"),
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1,
                    max_tokens=200,
                )
                response_text = completion.choices[0].message.content.strip()

                # Strip markdown code fences if present
                if response_text.startswith("```"):
                    response_text = "\n".join(response_text.split("\n")[1:-1])

                action = json.loads(response_text)

                # Normalize escalate field
                if isinstance(action.get("escalate"), str):
                    action["escalate"] = action["escalate"].lower() == "true"

                # Use heuristic confidence
                score = _compute_confidence(action)

            except Exception as e:
                action = {
                    "topic": "General Inquiry",
                    "priority": "medium",
                    "department": "customer_success",
                    "escalate": False,
                    "reasoning": f"Could not analyse: {str(e)[:50]}",
                }
                score = 0.0

            return {
                "email_id": email["email_id"],
                "sender": email["sender"],
                "subject": email["subject"],
                "body": email["body"][:300],
                "topic": action.get("topic", action.get("category", "General")),
                "priority": action.get("priority", "low"),
                "department": action.get("department", "general"),
                "escalate": action.get("escalate", False),
                "reasoning": action.get("reasoning", ""),
                "score": round(score, 2),
            }

        import asyncio
        results = await asyncio.gather(*(process_email(email) for email in emails))

        return {"results": list(results), "total": len(results), "next_page_token": next_page_token}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Entry Point ────────────────────────────────────────────

def main():
    """Entry point for running the server via `uv run server`."""
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