from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Any, Dict, Optional
from models import EmailObservation, EmailAction, EmailReward
from server.email_triage_env_environment import EmailTriageEnvEnvironment

app = FastAPI(
    title="Email Triage RL Environment",
    description=(
        "An OpenEnv-compatible reinforcement learning environment "
        "for training AI agents to triage and route emails. "
        "Built for the Meta x PyTorch OpenEnv Hackathon 2026."
    ),
    version="1.0.0",
)
app.mount("/static", StaticFiles(directory="frontend/static"), name="static")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
env = EmailTriageEnvEnvironment()
class ResetRequest(BaseModel):
    task_id: Optional[int] = None
class ResetResponse(BaseModel):
    observation: Dict[str, Any]
class StepRequest(BaseModel):
    action: Dict[str, Any]
class StepResponse(BaseModel):
    observation: Dict[str, Any]
    reward: Dict[str, Any]
    done: bool
    info: Dict[str, Any]
class StateResponse(BaseModel):
    state: Dict[str, Any]
# @app.get("/")
# def root():
#     return {
#         "name": "Email Triage RL Environment",
#         "version": "1.0.0",
#         "description": (
#             "Train AI agents to categorize, prioritize, "
#             "and route support emails."
#         ),
#         "tasks": {
#             "task_1": "Easy — categorize clearly written emails",
#             "task_2": "Medium — extract category, priority, department",
#             "task_3": "Hard — handle ambiguous emails with escalation",
#         },
#         "endpoints": ["/reset", "/step", "/state", "/health"],
#         "status": "running",
#     }



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

@app.get("/", response_class=HTMLResponse)
def landing():
    with open("frontend/index.html") as f:
        return f.read()

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard_page():
    with open("frontend/dashboard.html") as f:
        return f.read()

@app.get("/auth/login")
def auth_login():
    from server.gmail_service import get_auth_url
    url = get_auth_url()
    return RedirectResponse(url)

@app.get("/auth/callback")
def auth_callback(code: str, request: Request):
    from server.gmail_service import exchange_code
    token_data = exchange_code(code)
    from fastapi.responses import RedirectResponse as RR
    response = RR(url="/dashboard")
    response.set_cookie("token_data", __import__('json').dumps(token_data), httponly=True)
    return response
@app.get("/auth/me")
def auth_me(request: Request):
    import json
    token_data = request.cookies.get("token_data")
    if not token_data:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        td = json.loads(token_data)
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
    except Exception as e:
        return {"email": "Connected"}

@app.post("/triage")
def triage(request: Request):
    import json
    token_data = request.cookies.get("token_data")
    if not token_data:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        from server.gmail_service import fetch_emails
        td = json.loads(token_data)
        emails = fetch_emails(td, max_results=10)
        results = []
        for email in emails:
            env.reset(task_id=2)
            env.current_email = {
                **email,
                "task_id": 2,
                "task_description": "Triage this email.",
                "ground_truth": {
                    "category": "general_inquiry",
                    "priority": "medium",
                    "department": "customer_success",
                    "escalate": False,
                }
            }
            from server.email_triage_env_environment import (grade_task2, EmailTriageEnvEnvironment)
            import os
            from openai import OpenAI
            client_llm = OpenAI(
                base_url=os.getenv("API_BASE_URL", "https://router.huggingface.co/v1"),
                api_key=os.getenv("HF_TOKEN", ""),
            )
            prompt = f"""You are an email triage agent. Analyze this email and respond with ONLY valid JSON.

Subject: {email['subject']}
From: {email['sender']}
Body: {email['body'][:500]}

Required JSON:
{{"category": "billing|technical_support|complaint|general_inquiry|spam",
  "priority": "low|medium|high",
  "department": "finance|engineering|customer_success|sales|security",
  "escalate": true or false,
  "reasoning": "one sentence"}}"""
            try:
                completion = client_llm.chat.completions.create(
                    model=os.getenv("MODEL_NAME", "meta-llama/Llama-3.1-8B-Instruct"),
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1,
                    max_tokens=200,
                )
                response_text = completion.choices[0].message.content.strip()
                if response_text.startswith("```"):
                    response_text = "\n".join(response_text.split("\n")[1:-1])
                action = json.loads(response_text)
                if isinstance(action.get("escalate"), str):
                    action["escalate"] = action["escalate"].lower() == "true"
                from models import EmailAction
                email_action = EmailAction(**action)
                from server.email_triage_env_environment import grade_task2
                gt = {
                    "category": action["category"],
                    "priority": action["priority"],
                    "department": action["department"],
                    "escalate": action["escalate"],
                }
                reward = grade_task2(email_action, gt)
                score = reward.score
            except Exception:
                action = {
                    "category": "general_inquiry",
                    "priority": "medium",
                    "department": "customer_success",
                    "escalate": False,
                    "reasoning": "Could not analyse.",
                }
                score = 0.0

            results.append({
                "email_id": email["email_id"],
                "sender": email["sender"],
                "subject": email["subject"],
                "body": email["body"][:300],
                "category": action["category"],
                "priority": action["priority"],
                "department": action["department"],
                "escalate": action["escalate"],
                "reasoning": action.get("reasoning", ""),
                "score": score,
            })
        return {"results": results, "total": len(results)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
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