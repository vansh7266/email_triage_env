import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Any, Dict, Optional
from models import EmailObservation, EmailAction, EmailReward
from server.email_triage_env_environment import EmailTriageEnvEnvironment
from fastapi.responses import HTMLResponse

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


@app.get("/", response_class=HTMLResponse)
def root():
    return """<!DOCTYPE html>
<html>
<head>
    <title>Email Triage RL Environment</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { background: #0f172a; color: #e2e8f0; font-family: -apple-system, sans-serif; padding: 40px 20px; }
        .container { max-width: 900px; margin: 0 auto; }
        .header { text-align: center; margin-bottom: 40px; }
        .badge { background: #1e40af; color: #93c5fd; padding: 4px 12px; border-radius: 20px; font-size: 12px; display: inline-block; margin-bottom: 16px; }
        h1 { font-size: 36px; font-weight: 700; margin-bottom: 8px; }
        .subtitle { color: #94a3b8; font-size: 16px; }
        .cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 16px; margin-bottom: 32px; }
        .card { background: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 20px; }
        .card h3 { font-size: 14px; color: #94a3b8; margin-bottom: 8px; text-transform: uppercase; letter-spacing: 1px; }
        .card .value { font-size: 28px; font-weight: 700; color: #60a5fa; }
        .card .desc { font-size: 13px; color: #64748b; margin-top: 4px; }
        .section { background: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 24px; margin-bottom: 24px; }
        .section h2 { font-size: 18px; font-weight: 600; margin-bottom: 16px; color: #f1f5f9; }
        table { width: 100%; border-collapse: collapse; }
        th { text-align: left; padding: 10px 12px; font-size: 12px; color: #64748b; text-transform: uppercase; letter-spacing: 1px; border-bottom: 1px solid #334155; }
        td { padding: 12px; font-size: 14px; border-bottom: 1px solid #1e293b; }
        .method { background: #1d4ed8; color: #bfdbfe; padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: 600; }
        .method.get { background: #065f46; color: #6ee7b7; }
        .task-easy { color: #4ade80; }
        .task-medium { color: #facc15; }
        .task-hard { color: #f87171; }
        .try-it { background: #0f172a; border: 1px solid #334155; border-radius: 8px; padding: 16px; margin-top: 16px; }
        .try-it h3 { font-size: 14px; color: #94a3b8; margin-bottom: 12px; }
        button { background: #2563eb; color: white; border: none; padding: 10px 20px; border-radius: 8px; cursor: pointer; font-size: 14px; margin-right: 8px; margin-bottom: 8px; }
        button:hover { background: #1d4ed8; }
        pre { background: #0f172a; border: 1px solid #334155; border-radius: 8px; padding: 16px; font-size: 13px; color: #a5f3fc; overflow-x: auto; margin-top: 12px; white-space: pre-wrap; min-height: 60px; }
        .footer { text-align: center; color: #475569; font-size: 13px; margin-top: 40px; }
        .status-dot { width: 8px; height: 8px; background: #4ade80; border-radius: 50%; display: inline-block; margin-right: 6px; animation: pulse 2s infinite; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
    </style>
</head>
<body>
<div class="container">
    <div class="header">
        <div class="badge">Meta × PyTorch OpenEnv Hackathon 2026</div>
        <h1>📧 Email Triage RL Environment</h1>
        <p class="subtitle"><span class="status-dot"></span>Running · Team Exception · vansh7266/email_triage_env</p>
    </div>

    <div class="cards">
        <div class="card">
            <h3>Baseline Score</h3>
            <div class="value">0.67</div>
            <div class="desc">Overall average across 3 tasks</div>
        </div>
        <div class="card">
            <h3>Tasks</h3>
            <div class="value">3</div>
            <div class="desc">Easy → Medium → Hard</div>
        </div>
        <div class="card">
            <h3>Reward Range</h3>
            <div class="value">0.0 – 1.0</div>
            <div class="desc">Partial credit scoring</div>
        </div>
        <div class="card">
            <h3>Runtime</h3>
            <div class="value">~38s</div>
            <div class="desc">Full baseline evaluation</div>
        </div>
    </div>

    <div class="section">
        <h2>🔌 API Endpoints</h2>
        <table>
            <tr><th>Method</th><th>Endpoint</th><th>Description</th></tr>
            <tr><td><span class="method get">GET</span></td><td>/health</td><td>Health check — returns 200 if running</td></tr>
            <tr><td><span class="method">POST</span></td><td>/reset</td><td>Start new episode — returns email observation</td></tr>
            <tr><td><span class="method">POST</span></td><td>/step</td><td>Submit triage decision — returns reward + feedback</td></tr>
            <tr><td><span class="method get">GET</span></td><td>/state</td><td>Current environment state</td></tr>
            <tr><td><span class="method get">GET</span></td><td>/docs</td><td>Interactive API documentation</td></tr>
        </table>
    </div>

    <div class="section">
        <h2>🎯 Tasks</h2>
        <table>
            <tr><th>Task</th><th>Difficulty</th><th>Scoring</th><th>Expected Range</th></tr>
            <tr>
                <td>Basic Email Categorization</td>
                <td><span class="task-easy">Easy</span></td>
                <td>All-or-nothing per field</td>
                <td>0.5 – 1.0</td>
            </tr>
            <tr>
                <td>Multi-Field Extraction</td>
                <td><span class="task-medium">Medium</span></td>
                <td>Weighted average with partial credit</td>
                <td>0.3 – 0.9</td>
            </tr>
            <tr>
                <td>Complex Triage + Escalation</td>
                <td><span class="task-hard">Hard</span></td>
                <td>Escalation weighted 30%</td>
                <td>0.1 – 0.7</td>
            </tr>
        </table>
    </div>

    <div class="section">
        <h2>🧪 Try It Live</h2>
        <div class="try-it">
            <h3>Test the API directly from your browser</h3>
            <button onclick="testHealth()">GET /health</button>
            <button onclick="testReset()">POST /reset</button>
            <button onclick="testReset1()">POST /reset (Task 1)</button>
            <button onclick="testReset2()">POST /reset (Task 2)</button>
            <button onclick="testReset3()">POST /reset (Task 3)</button>
            <button onclick="testStep()">POST /step (sample)</button>
            <pre id="output">Click a button to test the API...</pre>
        </div>
    </div>

    <div class="footer">
        <p>Built by Team Exception — Vansh Gupta · Vineet Maheshwari · Anit Patel</p>
        <p style="margin-top:8px">Powered by OpenEnv · Meta · HuggingFace · PyTorch</p>
    </div>
</div>

<script>
async function call(method, path, body) {
    const out = document.getElementById('output');
    out.textContent = 'Loading...';
    try {
        const opts = { method, headers: {'Content-Type': 'application/json'} };
        if (body) opts.body = JSON.stringify(body);
        const r = await fetch(path, opts);
        const d = await r.json();
        out.textContent = JSON.stringify(d, null, 2);
    } catch(e) {
        out.textContent = 'Error: ' + e.message;
    }
}
function testHealth() { call('GET', '/health'); }
function testReset() { call('POST', '/reset', {}); }
function testReset1() { call('POST', '/reset', {task_id: 1}); }
function testReset2() { call('POST', '/reset', {task_id: 2}); }
function testReset3() { call('POST', '/reset', {task_id: 3}); }
function testStep() {
    call('POST', '/step', {action: {
        category: 'billing', priority: 'high',
        department: 'finance', escalate: false,
        reasoning: 'Invoice billing issue detected'
    }});
}
</script>
</body>
</html>"""
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