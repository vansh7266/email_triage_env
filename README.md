---
title: Email Triage RL Environment
emoji: 📧
colorFrom: blue
colorTo: green
sdk: docker
pinned: false
tags:
  - openenv
  - reinforcement-learning
  - email-triage
---

# 📧 Email Triage RL Environment

> A real-world reinforcement learning environment for training AI agents
> to categorize, prioritize, and route support emails.
> Built for the **Meta × PyTorch OpenEnv Hackathon 2026** by **Team Exception**.

---

## 🌍 Real-World Problem

Every company with a customer support team faces the same challenge:
hundreds of emails arrive daily and must be:

1. **Categorized** — Is this a billing issue? A technical bug? Spam?
2. **Prioritized** — How urgently does this need a response?
3. **Routed** — Which department should handle it?
4. **Escalated** — Does a human manager need to see this immediately?

Currently, junior support agents spend hours doing this manually.
This environment trains AI agents to automate exactly this workflow —
the same workflow used at companies like Flipkart, Zomato, and thousands
of SaaS businesses worldwide.

---

## 🏗️ Environment Overview

| Property | Value |
|---|---|
| Framework | OpenEnv (Meta × HuggingFace) |
| Task Type | NLP Classification + Routing |
| Action Space | Discrete (category, priority, department, escalate) |
| Observation Space | Structured text (email content + metadata) |
| Reward Range | 0.0 → 1.0 |
| Episodes | 1 step per episode |
| Tasks | 3 (Easy → Medium → Hard) |

---

## 🎯 Three Tasks

### Task 1 — Basic Email Categorization (Easy)
The agent receives a clearly written email with obvious intent.
Must identify category, priority, department, and escalation need.

- **Scoring:** All-or-nothing per field. Score = average of 4 sub-scores.
- **Expected score range:** 0.5 → 1.0
- **Example:** An email saying "Invoice #1042 is wrong, please refund"
  → clearly `billing`, `high` priority, `finance` department

### Task 2 — Multi-Field Extraction (Medium)
Emails require careful reading. Intent is less obvious.
Priority gets partial credit if one level off.

- **Scoring:** Weighted average — category 35%, priority 25%,
  department 25%, escalation 15%
- **Expected score range:** 0.3 → 0.9
- **Example:** An email about a subscription question that turns out
  to be a double-billing complaint

### Task 3 — Complex Triage with Escalation (Hard)
Ambiguous emails with multiple issues, legal threats, churn risk,
or security concerns. Escalation decisions carry heavy weight.
**Missing a required escalation = maximum penalty.**

- **Scoring:** Weighted average — category 30%, priority 20%,
  department 20%, escalation 30%
- **Expected score range:** 0.1 → 0.7
- **Example:** An email from a CFO with both a potential data breach
  AND an overdue $45,000 invoice threatening legal action

---

## 📐 Action Space

The agent must return a JSON action with these exact fields:
```json
{
    "category": "billing | technical_support | complaint | general_inquiry | spam",
    "priority": "low | medium | high",
    "department": "finance | engineering | customer_success | sales | security",
    "escalate": true or false,
    "reasoning": "One sentence explanation"
}
```

---

## 👁️ Observation Space

The agent receives a JSON observation with these fields:
```json
{
    "email_id": "email_001",
    "sender": "user@example.com",
    "subject": "Invoice is incorrect",
    "body": "Full email body text...",
    "urgency_hint": "high or null",
    "task_id": 1,
    "task_description": "Instructions for the agent",
    "done": false
}
```

---

## 🏆 Reward Structure
```
Task 1 (Easy):
  score = (category + priority + department + escalation) / 4

Task 2 (Medium):
  score = category×0.35 + priority×0.25 + department×0.25 + escalation×0.15
  priority: exact=1.0, one level off=0.5, two levels off=0.0

Task 3 (Hard):
  score = category×0.30 + priority×0.20 + department×0.20 + escalation×0.30
  missed escalation when required = 0.0 on escalation sub-score
```

---

## 🚀 Quick Start

### Option 1 — Run Locally
```bash
# 1. Clone the repo
git clone https://huggingface.co/spaces/YOUR_USERNAME/email_triage_env
cd email_triage_env

# 2. Install dependencies
pip install -r server/requirements.txt

# 3. Start the server
uvicorn server.app:app --host 0.0.0.0 --port 8000

# 4. Test it's working
curl http://localhost:8000/health
curl -X POST http://localhost:8000/reset
```

### Option 2 — Run with Docker
```bash
# 1. Build the container
docker build -t email_triage_env:latest -f server/Dockerfile .

# 2. Run the container
docker run -p 8000:8000 email_triage_env:latest

# 3. Test it's working
curl http://localhost:8000/health
```

---

## 🤖 Running the Baseline Inference Script
```bash
# Set required environment variables
export API_BASE_URL="https://api-inference.huggingface.co/v1"
export MODEL_NAME="mistralai/Mistral-7B-Instruct-v0.3"
export HF_TOKEN="your_huggingface_token"

# Make sure the environment server is running first
# Then run the inference script
python inference.py
```

Expected output:
```
============================================================
  Email Triage RL Environment — Baseline Evaluation
  Team Exception | OpenEnv Hackathon 2026
============================================================

Task 1 (Easy — Basic Categorization)        avg=0.83  min=0.50  max=1.00
Task 2 (Medium — Multi-Field Extraction)    avg=0.61  min=0.35  max=0.90
Task 3 (Hard — Complex Triage)              avg=0.38  min=0.10  max=0.60

Overall Average Score: 0.61
```

---

## 📁 Project Structure
```
email_triage_env/
│
├── models.py                          # Pydantic models (Observation, Action, Reward)
├── openenv.yaml                       # OpenEnv metadata and spec
├── inference.py                       # Baseline inference script (MANDATORY)
├── baseline_scores.json               # Generated by inference.py
├── README.md                          # This file
├── pyproject.toml                     # Project config
│
└── server/
    ├── app.py                         # FastAPI web server
    ├── email_triage_env_environment.py # Core environment logic
    ├── requirements.txt               # Python dependencies
    └── Dockerfile                     # Container definition
```

---

## 🔌 API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/` | Environment info |
| GET | `/health` | Health check — returns 200 if running |
| POST | `/reset` | Start new episode — returns email observation |
| POST | `/step` | Submit action — returns reward + feedback |
| GET | `/state` | Current environment state |

### Example API Usage
```python
import requests

# Start a new episode
obs = requests.post("http://localhost:8000/reset").json()
print(obs["observation"]["subject"])

# Submit an action
action = {
    "action": {
        "category": "billing",
        "priority": "high",
        "department": "finance",
        "escalate": False,
        "reasoning": "Email is about an incorrect invoice charge."
    }
}
result = requests.post("http://localhost:8000/step", json=action).json()
print(f"Score: {result['reward']['score']}")
print(f"Feedback: {result['reward']['feedback']}")
```

---

## 🔮 Real-World Extension

This environment is architected for seamless integration
with live email systems. To connect to a real Gmail inbox,
only the data layer needs to change — all environment
logic, grading, and reward functions remain identical:
```python
# Current (hackathon): synthetic emails
self.current_email = random.choice(EMAIL_DATASET)

# Future (production): real Gmail API
# service = build('gmail', 'v1', credentials=creds)
# self.current_email = fetch_and_parse_latest_email(service)
```

---

## 👥 Team

**Team Exception**
- Vansh Gupta (Team Lead)
- Vineet Maheshwari
- Anit Patel

Built for the Meta × PyTorch OpenEnv Hackathon 2026
Powered by Scaler School of Technology