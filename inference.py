import os
import json
import time
import requests
from openai import OpenAI
API_BASE_URL = os.getenv("API_BASE_URL", "https://api-inference.huggingface.co/v1")
API_KEY      = os.getenv("HF_TOKEN") or os.getenv("API_KEY", "hf_placeholder")
MODEL_NAME   = os.getenv("MODEL_NAME", "mistralai/Mistral-7B-Instruct-v0.3")
ENV_BASE_URL = os.getenv("ENV_BASE_URL", "http://localhost:8000")
EPISODES_PER_TASK = 3
TEMPERATURE = 0.1
MAX_TOKENS  = 300
client = OpenAI(
    base_url=API_BASE_URL,
    api_key=API_KEY,
)
def env_reset(task_id: int = None) -> dict:
    payload = {}
    if task_id is not None:
        payload["task_id"] = task_id
    response = requests.post(f"{ENV_BASE_URL}/reset", json=payload)
    response.raise_for_status()
    return response.json()
def env_step(action: dict) -> dict:
    response = requests.post(
        f"{ENV_BASE_URL}/step",
        json={"action": action}
    )
    response.raise_for_status()
    return response.json()
def env_state() -> dict:
    response = requests.get(f"{ENV_BASE_URL}/state")
    response.raise_for_status()
    return response.json()
def env_health() -> bool:
    try:
        response = requests.get(f"{ENV_BASE_URL}/health", timeout=5)
        return response.status_code == 200
    except Exception:
        return False
def build_agent_prompt(observation: dict) -> str:
    prompt = f"""You are an expert email triage agent for a customer support team.
Your job is to analyze the incoming email and make a triage decision.
=== INCOMING EMAIL ===
Email ID: {observation.get('email_id', 'unknown')}
From: {observation.get('sender', 'unknown')}
Subject: {observation.get('subject', 'unknown')}
Body:
{observation.get('body', 'unknown')}
=== YOUR TASK ===
{observation.get('task_description', 'Categorize this email.')}
=== INSTRUCTIONS ===
You must respond with ONLY a valid JSON object. No explanation before or after.
Choose values EXACTLY from the allowed options listed below.
Required JSON format:
{{
    "category": "<one of: billing | technical_support | complaint | general_inquiry | spam>",
    "priority": "<one of: low | medium | high>",
    "department": "<one of: finance | engineering | customer_success | sales | security>",
    "escalate": <true or false>,
    "reasoning": "<one sentence explaining your decision>"
}}
Rules:
- category MUST be exactly one of: billing, technical_support, complaint, general_inquiry, spam
- priority MUST be exactly one of: low, medium, high
- department MUST be exactly one of: finance, engineering, customer_success, sales, security
- escalate MUST be exactly true or false (boolean, not string)
- reasoning MUST be a non-empty string
Respond with ONLY the JSON object. Nothing else."""
    return prompt
def run_agent(observation: dict) -> dict:
    prompt = build_agent_prompt(observation)
    try:
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an email triage agent. "
                        "Always respond with valid JSON only. "
                        "No markdown, no explanation, just JSON."
                    )
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
        )
        response_text = completion.choices[0].message.content.strip()
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            response_text = "\n".join(lines[1:-1])
        action = json.loads(response_text)
        if isinstance(action.get("escalate"), str):
            action["escalate"] = action["escalate"].lower() == "true"
        return action
    except json.JSONDecodeError as e:
        print(f"  [WARNING] JSON parse error: {e}")
        print(f"  [WARNING] Raw response: {response_text[:200]}")
        return {
            "category": "general_inquiry",
            "priority": "low",
            "department": "customer_success",
            "escalate": False,
            "reasoning": "Fallback action due to JSON parse error.",
        }
    except Exception as e:
        print(f"  [WARNING] LLM call failed: {e}")
        return {
            "category": "general_inquiry",
            "priority": "low",
            "department": "customer_success",
            "escalate": False,
            "reasoning": "Fallback action due to API error.",
        }
def run_task_episodes(task_name: str, n_episodes: int, task_id: int = None) -> dict:
    print(f"\n{'='*50}")
    print(f"Running {task_name} ({n_episodes} episodes)")
    print(f"{'='*50}")
    scores = []
    episode_details = []
    for episode in range(1, n_episodes + 1):
        print(f"\n  Episode {episode}/{n_episodes}:")
        reset_result = env_reset(task_id=task_id)
        observation = reset_result["observation"]
        print(f"  Email: [{observation.get('email_id')}] "
              f"{observation.get('subject', '')[:50]}")
        print(f"  Task ID: {observation.get('task_id')}")
        action = run_agent(observation)
        print(f"  Agent decided: category={action.get('category')} | "
              f"priority={action.get('priority')} | "
              f"dept={action.get('department')} | "
              f"escalate={action.get('escalate')}")
        step_result = env_step(action)
        reward = step_result["reward"]
        score = reward.get("score", 0.0)
        feedback = reward.get("feedback", "")
        scores.append(score)
        episode_details.append({
            "episode": episode,
            "email_id": observation.get("email_id"),
            "task_id": observation.get("task_id"),
            "action": action,
            "score": score,
            "feedback": feedback,
        })
        print(f"  Score: {score:.2f}")
        print(f"  Feedback: {feedback[:100]}")
        time.sleep(0.5)
    avg_score = sum(scores) / len(scores) if scores else 0.0
    min_score = min(scores) if scores else 0.0
    max_score = max(scores) if scores else 0.0
    print(f"\n  {task_name} Results:")
    print(f"  Average Score: {avg_score:.2f}")
    print(f"  Min Score:     {min_score:.2f}")
    print(f"  Max Score:     {max_score:.2f}")
    print(f"  All Scores:    {[round(s, 2) for s in scores]}")
    return {
        "task": task_name,
        "episodes": n_episodes,
        "average_score": round(avg_score, 2),
        "min_score": round(min_score, 2),
        "max_score": round(max_score, 2),
        "scores": [round(s, 2) for s in scores],
        "details": episode_details,
    }
def main():
    print("\n" + "="*60)
    print("  Email Triage RL Environment — Baseline Evaluation")
    print("  Team Exception | OpenEnv Hackathon 2026")
    print("="*60)
    print(f"\nChecking environment at {ENV_BASE_URL}...")
    if not env_health():
        print(f"ERROR: Environment server not running at {ENV_BASE_URL}")
        print("Please start the server first:")
        print("  cd email_triage_env")
        print("  uvicorn server.app:app --host 0.0.0.0 --port 8000")
        return
    print("Environment is running!")
    print(f"\nConfiguration:")
    print(f"  API_BASE_URL:  {API_BASE_URL}")
    print(f"  MODEL_NAME:    {MODEL_NAME}")
    print(f"  ENV_BASE_URL:  {ENV_BASE_URL}")
    print(f"  Episodes/task: {EPISODES_PER_TASK}")
    start_time = time.time()
    all_results = []
    task1_results = run_task_episodes(
        "Task 1 (Easy — Basic Categorization)",
        EPISODES_PER_TASK,
        task_id=1
    )
    all_results.append(task1_results)
    task2_results = run_task_episodes(
        "Task 2 (Medium — Multi-Field Extraction)",
        EPISODES_PER_TASK,
        task_id=2
    )
    all_results.append(task2_results)
    task3_results = run_task_episodes(
        "Task 3 (Hard — Complex Triage with Escalation)",
        EPISODES_PER_TASK,
        task_id=3
    )
    all_results.append(task3_results)
    elapsed = time.time() - start_time
    print("\n" + "="*60)
    print("  FINAL BASELINE SCORES")
    print("="*60)
    for result in all_results:
        print(f"  {result['task']:<45} "
              f"avg={result['average_score']:.2f}  "
              f"min={result['min_score']:.2f}  "
              f"max={result['max_score']:.2f}")
    overall_avg = sum(r["average_score"] for r in all_results) / len(all_results)
    print(f"\n  Overall Average Score: {overall_avg:.2f}")
    print(f"  Total Runtime: {elapsed:.1f}s")
    print("="*60)
    output = {
        "environment": "email_triage_env",
        "team": "Team Exception",
        "model": MODEL_NAME,
        "overall_average_score": round(overall_avg, 2),
        "total_runtime_seconds": round(elapsed, 1),
        "task_results": all_results,
    }
    with open("baseline_scores.json", "w") as f:
        json.dump(output, f, indent=2)
    print("\nResults saved to baseline_scores.json")
    print("\nBaseline evaluation complete!")
if __name__ == "__main__":
    main()