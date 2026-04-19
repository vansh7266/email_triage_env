import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from models import EmailAction
from server.email_triage_env_environment import (
    grade_task1, grade_task2, grade_task3
)

GROUND_TRUTH_1 = {
    "category": "billing",
    "priority": "high",
    "department": "finance",
    "escalate": False,
}

def make_action(**kwargs):
    defaults = {
        "category": "billing",
        "priority": "high",
        "department": "finance",
        "escalate": False,
        "reasoning": "test",
    }
    defaults.update(kwargs)
    return EmailAction(**defaults)

def test_task1_perfect_score():
    action = make_action()
    reward = grade_task1(action, GROUND_TRUTH_1)
    assert reward.score == 1.0

def test_task1_all_wrong():
    action = make_action(
        category="spam",
        priority="low",
        department="security",
        escalate=True
    )
    reward = grade_task1(action, GROUND_TRUTH_1)
    assert reward.score == 0.0

def test_task1_half_score():
    action = make_action(category="spam", priority="low")
    reward = grade_task1(action, GROUND_TRUTH_1)
    assert reward.score == 0.5

def test_task2_partial_priority_credit():
    action = make_action(priority="medium")
    reward = grade_task2(action, GROUND_TRUTH_1)
    assert reward.priority_score == 0.5

def test_task2_two_levels_off():
    action = make_action(priority="low")
    reward = grade_task2(action, GROUND_TRUTH_1)
    assert reward.priority_score == 0.0

def test_task3_missed_escalation_penalty():
    gt = {**GROUND_TRUTH_1, "escalate": True}
    action = make_action(escalate=False)
    reward = grade_task3(action, gt)
    assert reward.escalation_score == 0.0

def test_task3_unnecessary_escalation_minor_penalty():
    action = make_action(escalate=True)
    reward = grade_task3(action, GROUND_TRUTH_1)
    assert reward.escalation_score == 0.3

def test_all_rewards_in_range():
    for action_kwargs in [
        {},
        {"category": "spam"},
        {"priority": "low"},
        {"escalate": True},
    ]:
        action = make_action(**action_kwargs)
        for grade_fn in [grade_task1, grade_task2, grade_task3]:
            reward = grade_fn(action, GROUND_TRUTH_1)
            assert 0.0 <= reward.score <= 1.0, f"Score out of range: {reward.score}"