import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fastapi import FastAPI, HTTPException
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
@app.get("/")
def root():
    return {
        "name": "Email Triage RL Environment",
        "version": "1.0.0",
        "description": (
            "Train AI agents to categorize, prioritize, "
            "and route support emails."
        ),
        "tasks": {
            "task_1": "Easy — categorize clearly written emails",
            "task_2": "Medium — extract category, priority, department",
            "task_3": "Hard — handle ambiguous emails with escalation",
        },
        "endpoints": ["/reset", "/step", "/state", "/health"],
        "status": "running",
    }
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