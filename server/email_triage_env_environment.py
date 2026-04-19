import random
from typing import Any
from models import EmailObservation, EmailAction, EmailReward
EMAIL_DATASET = [
    {
        "email_id": "email_001",
        "sender": "john.doe@gmail.com",
        "subject": "Invoice #1042 is incorrect",
        "body": (
            "Hello, I received invoice #1042 and the amount charged "
            "is wrong. I was supposed to be charged $49 but you charged "
            "$149. Please correct this and issue a refund immediately."
        ),
        "urgency_hint": "high",
        "task_id": 1,
        "task_description": (
            "Categorize this email. Choose exactly one category from: "
            "billing, technical_support, complaint, general_inquiry, spam. "
            "Also set priority (low/medium/high), department, escalate (true/false), "
            "and a short reasoning."
        ),
        "ground_truth": {
            "category": "billing",
            "priority": "high",
            "department": "finance",
            "escalate": False,
        },
    },
    {
        "email_id": "email_002",
        "sender": "priya.sharma@hotmail.com",
        "subject": "Cannot login to my account",
        "body": (
            "Hi support team, I have been trying to login to my account "
            "since yesterday but I keep getting an error that says "
            "'Invalid credentials'. I have tried resetting my password "
            "twice but the problem persists. Please help."
        ),
        "urgency_hint": "medium",
        "task_id": 1,
        "task_description": (
            "Categorize this email. Choose exactly one category from: "
            "billing, technical_support, complaint, general_inquiry, spam. "
            "Also set priority (low/medium/high), department, escalate (true/false), "
            "and a short reasoning."
        ),
        "ground_truth": {
            "category": "technical_support",
            "priority": "medium",
            "department": "engineering",
            "escalate": False,
        },
    },
    {
        "email_id": "email_003",
        "sender": "noreply@spam123.net",
        "subject": "You have WON $1,000,000!!!",
        "body": (
            "Congratulations!!! You have been selected as our lucky winner. "
            "Click this link immediately to claim your $1,000,000 prize. "
            "Offer expires in 24 hours. Act NOW!!!"
        ),
        "urgency_hint": "low",
        "task_id": 1,
        "task_description": (
            "Categorize this email. Choose exactly one category from: "
            "billing, technical_support, complaint, general_inquiry, spam. "
            "Also set priority (low/medium/high), department, escalate (true/false), "
            "and a short reasoning."
        ),
        "ground_truth": {
            "category": "spam",
            "priority": "low",
            "department": "security",
            "escalate": False,
        },
    },
    {
        "email_id": "email_004",
        "sender": "amit.verma@company.org",
        "subject": "Question about subscription",
        "body": (
            "Hello, I recently upgraded my plan from Basic to Pro. "
            "However, I noticed I was charged twice this month — once "
            "for Basic and once for Pro. Could you clarify the billing "
            "cycle and refund the extra charge? Also, when does my Pro "
            "plan start officially?"
        ),
        "urgency_hint": None,
        "task_id": 2,
        "task_description": (
            "This email requires careful reading. Determine: category "
            "(billing/technical_support/complaint/general_inquiry/spam), "
            "priority (low/medium/high), department to route to "
            "(finance/engineering/customer_success/sales/security), "
            "whether to escalate, and your reasoning."
        ),
        "ground_truth": {
            "category": "billing",
            "priority": "medium",
            "department": "finance",
            "escalate": False,
        },
    },
    {
        "email_id": "email_005",
        "sender": "sarah.jones@enterprise.com",
        "subject": "API rate limits affecting our production app",
        "body": (
            "We are an enterprise customer and our production application "
            "has been hitting API rate limits since 2 AM today. This is "
            "causing serious disruption to our 50,000 users. Our CTO has "
            "been notified. We need this resolved in the next 2 hours or "
            "we will need to escalate to our account manager."
        ),
        "urgency_hint": None,
        "task_id": 2,
        "task_description": (
            "This email requires careful reading. Determine: category "
            "(billing/technical_support/complaint/general_inquiry/spam), "
            "priority (low/medium/high), department to route to "
            "(finance/engineering/customer_success/sales/security), "
            "whether to escalate, and your reasoning."
        ),
        "ground_truth": {
            "category": "technical_support",
            "priority": "high",
            "department": "engineering",
            "escalate": True,
        },
    },
    {
        "email_id": "email_006",
        "sender": "cfo@bigclient.com",
        "subject": "Urgent: Data breach concern + unpaid invoice",
        "body": (
            "Dear Team, I am writing with two urgent concerns. "
            "First, our security team detected unusual API access patterns "
            "from your platform at 3 AM last night which may indicate a "
            "data breach affecting our confidential records. "
            "Second, we have an overdue invoice of $45,000 from last month "
            "that has not been processed yet despite three follow-ups. "
            "Both issues need immediate CEO-level attention. "
            "If not resolved within 24 hours, we will engage our lawyers."
        ),
        "urgency_hint": None,
        "task_id": 3,
        "task_description": (
            "This is a complex email with multiple issues and legal threat. "
            "Determine the PRIMARY category, appropriate priority, best "
            "department to handle it first, whether immediate human "
            "escalation is needed, and detailed reasoning. "
            "Note: security concerns involving possible data breach always "
            "require escalation regardless of other factors."
        ),
        "ground_truth": {
            "category": "complaint",
            "priority": "high",
            "department": "security",
            "escalate": True,
        },
    },
    {
        "email_id": "email_007",
        "sender": "user99@personal.com",
        "subject": "Not happy",
        "body": (
            "I have been a customer for 3 years and I am very disappointed. "
            "Your latest update broke the export feature I use every day. "
            "I tried contacting support last week but nobody replied. "
            "I am now considering switching to your competitor unless "
            "someone actually helps me."
        ),
        "urgency_hint": None,
        "task_id": 3,
        "task_description": (
            "This is a complex email with churn risk. "
            "Determine the PRIMARY category, appropriate priority, best "
            "department to handle it, whether immediate human escalation "
            "is needed, and detailed reasoning. "
            "Note: long-term customers expressing churn intent require "
            "special handling."
        ),
        "ground_truth": {
            "category": "complaint",
            "priority": "high",
            "department": "customer_success",
            "escalate": True,
        },
    },

    # ── HEALTHCARE EMAILS ─────────────────────────────────
    {
        "email_id": "email_008",
        "sender": "patient.rahul@gmail.com",
        "subject": "Wrong medication in my order",
        "body": (
            "Hello, I received my monthly medication delivery today but "
            "the dosage is completely wrong. I was prescribed 10mg tablets "
            "but received 50mg. This is dangerous. Please fix immediately."
        ),
        "urgency_hint": "high",
        "task_id": 1,
        "task_description": (
            "Categorize this email. Choose exactly one category from: "
            "billing, technical_support, complaint, general_inquiry, spam. "
            "Also set priority (low/medium/high), department, escalate (true/false), "
            "and a short reasoning."
        ),
        "ground_truth": {
            "category": "complaint",
            "priority": "high",
            "department": "customer_success",
            "escalate": True,
        },
    },
    {
        "email_id": "email_009",
        "sender": "dr.mehta@hospital.org",
        "subject": "API integration for patient records",
        "body": (
            "We are a hospital trying to integrate your API with our "
            "patient records system. We have been following the documentation "
            "but keep getting 403 errors on the /records endpoint. "
            "Can you help us set up the correct authentication?"
        ),
        "urgency_hint": "medium",
        "task_id": 1,
        "task_description": (
            "Categorize this email. Choose exactly one category from: "
            "billing, technical_support, complaint, general_inquiry, spam. "
            "Also set priority (low/medium/high), department, escalate (true/false), "
            "and a short reasoning."
        ),
        "ground_truth": {
            "category": "technical_support",
            "priority": "medium",
            "department": "engineering",
            "escalate": False,
        },
    },
    # ── E-COMMERCE EMAILS ─────────────────────────────────
    {
        "email_id": "email_010",
        "sender": "shopper.priya@gmail.com",
        "subject": "Wrong item delivered",
        "body": (
            "I ordered a blue Nike running shoe size 8 but received "
            "a red Adidas shoe size 9. Order #ORD-48291. I need the "
            "correct item urgently as it was a birthday gift."
        ),
        "urgency_hint": "high",
        "task_id": 1,
        "task_description": (
            "Categorize this email. Choose exactly one category from: "
            "billing, technical_support, complaint, general_inquiry, spam. "
            "Also set priority (low/medium/high), department, escalate (true/false), "
            "and a short reasoning."
        ),
        "ground_truth": {
            "category": "complaint",
            "priority": "high",
            "department": "customer_success",
            "escalate": False,
        },
    },
    {
        "email_id": "email_011",
        "sender": "seller.amit@shop.com",
        "subject": "How do I list bulk products?",
        "body": (
            "Hi, I am a new seller on your platform. I have around 500 "
            "products to list. Is there a bulk upload feature? "
            "I could not find it in the seller dashboard."
        ),
        "urgency_hint": "low",
        "task_id": 1,
        "task_description": (
            "Categorize this email. Choose exactly one category from: "
            "billing, technical_support, complaint, general_inquiry, spam. "
            "Also set priority (low/medium/high), department, escalate (true/false), "
            "and a short reasoning."
        ),
        "ground_truth": {
            "category": "general_inquiry",
            "priority": "low",
            "department": "sales",
            "escalate": False,
        },
    },
    # ── HR / INTERNAL EMAILS ──────────────────────────────
    {
        "email_id": "email_012",
        "sender": "employee.neha@company.com",
        "subject": "Salary not credited for October",
        "body": (
            "My salary for October has not been credited yet. "
            "Today is the 10th of November. I have already raised "
            "this with my manager but got no response. "
            "Please look into this urgently."
        ),
        "urgency_hint": "high",
        "task_id": 2,
        "task_description": (
            "This email requires careful reading. Determine: category "
            "(billing/technical_support/complaint/general_inquiry/spam), "
            "priority (low/medium/high), department to route to "
            "(finance/engineering/customer_success/sales/security), "
            "whether to escalate, and your reasoning."
        ),
        "ground_truth": {
            "category": "billing",
            "priority": "high",
            "department": "finance",
            "escalate": True,
        },
    },
    {
        "email_id": "email_013",
        "sender": "intern.ravi@company.com",
        "subject": "Laptop access issue",
        "body": (
            "I joined last week as an intern and my laptop still does not "
            "have access to the internal dev tools. I cannot push code to "
            "the repository. My manager is Ankit Sharma. Please help."
        ),
        "urgency_hint": "medium",
        "task_id": 2,
        "task_description": (
            "This email requires careful reading. Determine: category "
            "(billing/technical_support/complaint/general_inquiry/spam), "
            "priority (low/medium/high), department to route to "
            "(finance/engineering/customer_success/sales/security), "
            "whether to escalate, and your reasoning."
        ),
        "ground_truth": {
            "category": "technical_support",
            "priority": "medium",
            "department": "engineering",
            "escalate": False,
        },
    },
    # ── BANKING EMAILS ────────────────────────────────────
    {
        "email_id": "email_014",
        "sender": "customer.vikram@gmail.com",
        "subject": "Unauthorized transaction on my account",
        "body": (
            "There is a transaction of Rs 45,000 on my account that I "
            "did not make. It was done at 3 AM last night from a location "
            "I have never been to. I think my card has been cloned. "
            "Please block my card and investigate immediately."
        ),
        "urgency_hint": None,
        "task_id": 3,
        "task_description": (
            "This is a complex email with potential fraud. "
            "Determine the PRIMARY category, appropriate priority, best "
            "department to handle it first, whether immediate human "
            "escalation is needed, and detailed reasoning. "
            "Note: potential fraud always requires immediate escalation."
        ),
        "ground_truth": {
            "category": "complaint",
            "priority": "high",
            "department": "security",
            "escalate": True,
        },
    },
    {
        "email_id": "email_015",
        "sender": "business.owner@startup.in",
        "subject": "Need to upgrade plan but website is down",
        "body": (
            "I have been trying to upgrade my subscription from Basic to "
            "Enterprise for the past 2 days but your payment page keeps "
            "crashing. I am losing customers because of the feature limits. "
            "This is costing me money every hour. Fix this NOW."
        ),
        "urgency_hint": None,
        "task_id": 3,
        "task_description": (
            "This is a complex email with both a technical issue and "
            "business urgency. Determine the PRIMARY category, appropriate "
            "priority, best department, whether to escalate, and reasoning. "
            "Note: revenue-impacting issues need expedited handling."
        ),
        "ground_truth": {
            "category": "technical_support",
            "priority": "high",
            "department": "engineering",
            "escalate": True,
        },
    },
]
def grade_task1(action: EmailAction, ground_truth: dict) -> EmailReward:
    cat_score = 1.0 if action.category == ground_truth["category"] else 0.0
    pri_score = 1.0 if action.priority == ground_truth["priority"] else 0.0
    dep_score = 1.0 if action.department == ground_truth["department"] else 0.0
    esc_score = 1.0 if action.escalate == ground_truth["escalate"] else 0.0
    total = (cat_score + pri_score + dep_score + esc_score) / 4.0
    feedback_parts = []
    if cat_score == 1.0:
        feedback_parts.append("✓ Category correct")
    else:
        feedback_parts.append(
            f"✗ Category wrong (got '{action.category}', "
            f"expected '{ground_truth['category']}')"
        )
    if pri_score == 1.0:
        feedback_parts.append("✓ Priority correct")
    else:
        feedback_parts.append(
            f"✗ Priority wrong (got '{action.priority}', "
            f"expected '{ground_truth['priority']}')"
        )
    if dep_score == 1.0:
        feedback_parts.append("✓ Department correct")
    else:
        feedback_parts.append(
            f"✗ Department wrong (got '{action.department}', "
            f"expected '{ground_truth['department']}')"
        )
    if esc_score == 1.0:
        feedback_parts.append("✓ Escalation correct")
    else:
        feedback_parts.append(
            f"✗ Escalation wrong (got {action.escalate}, "
            f"expected {ground_truth['escalate']})"
        )
    return EmailReward(
        score=round(total, 2),
        category_score=cat_score,
        priority_score=pri_score,
        department_score=dep_score,
        escalation_score=esc_score,
        feedback=" | ".join(feedback_parts),
    )
def grade_task2(action: EmailAction, ground_truth: dict) -> EmailReward:
    cat_score = 1.0 if action.category == ground_truth["category"] else 0.0
    priority_order = ["low", "medium", "high"]
    try:
        got_idx = priority_order.index(action.priority)
        exp_idx = priority_order.index(ground_truth["priority"])
        diff = abs(got_idx - exp_idx)
        if diff == 0:
            pri_score = 1.0
        elif diff == 1:
            pri_score = 0.5
        else:
            pri_score = 0.0
    except ValueError:
        pri_score = 0.0
    dep_score = 1.0 if action.department == ground_truth["department"] else 0.0
    esc_score = 1.0 if action.escalate == ground_truth["escalate"] else 0.0
    total = (
        cat_score * 0.35 +
        pri_score * 0.25 +
        dep_score * 0.25 +
        esc_score * 0.15
    )
    feedback_parts = []
    feedback_parts.append(
        f"Category: {'✓' if cat_score == 1.0 else '✗'} "
        f"(got '{action.category}', expected '{ground_truth['category']}')"
    )
    feedback_parts.append(
        f"Priority: {'✓' if pri_score == 1.0 else ('~' if pri_score == 0.5 else '✗')} "
        f"(got '{action.priority}', expected '{ground_truth['priority']}')"
    )
    feedback_parts.append(
        f"Department: {'✓' if dep_score == 1.0 else '✗'} "
        f"(got '{action.department}', expected '{ground_truth['department']}')"
    )
    feedback_parts.append(
        f"Escalation: {'✓' if esc_score == 1.0 else '✗'} "
        f"(got {action.escalate}, expected {ground_truth['escalate']})"
    )
    return EmailReward(
        score=round(total, 2),
        category_score=cat_score,
        priority_score=pri_score,
        department_score=dep_score,
        escalation_score=esc_score,
        feedback=" | ".join(feedback_parts),
    )
def grade_task3(action: EmailAction, ground_truth: dict) -> EmailReward:
    cat_score = 1.0 if action.category == ground_truth["category"] else 0.0
    priority_order = ["low", "medium", "high"]
    try:
        got_idx = priority_order.index(action.priority)
        exp_idx = priority_order.index(ground_truth["priority"])
        diff = abs(got_idx - exp_idx)
        if diff == 0:
            pri_score = 1.0
        elif diff == 1:
            pri_score = 0.5
        else:
            pri_score = 0.0
    except ValueError:
        pri_score = 0.0
    dep_score = 1.0 if action.department == ground_truth["department"] else 0.0
    if action.escalate == ground_truth["escalate"]:
        esc_score = 1.0
    elif ground_truth["escalate"] is True and action.escalate is False:
        esc_score = 0.0
    else:
        esc_score = 0.3
    total = (
        cat_score * 0.30 +
        pri_score * 0.20 +
        dep_score * 0.20 +
        esc_score * 0.30
    )
    feedback_parts = []
    feedback_parts.append(
        f"Category: {'✓' if cat_score == 1.0 else '✗'} "
        f"(got '{action.category}', expected '{ground_truth['category']}')"
    )
    feedback_parts.append(
        f"Priority: {'✓' if pri_score == 1.0 else ('~' if pri_score == 0.5 else '✗')} "
        f"(got '{action.priority}', expected '{ground_truth['priority']}')"
    )
    feedback_parts.append(
        f"Department: {'✓' if dep_score == 1.0 else '✗'} "
        f"(got '{action.department}', expected '{ground_truth['department']}')"
    )
    if esc_score == 1.0:
        feedback_parts.append("Escalation: ✓ Correct")
    elif esc_score == 0.0:
        feedback_parts.append(
            "Escalation: ✗ CRITICAL MISS — should have escalated!"
        )
    else:
        feedback_parts.append(
            "Escalation: ~ Unnecessary escalation (minor penalty)"
        )
    return EmailReward(
        score=round(total, 2),
        category_score=cat_score,
        priority_score=pri_score,
        department_score=dep_score,
        escalation_score=esc_score,
        feedback=" | ".join(feedback_parts),
    )
class EmailTriageEnvEnvironment:
    def __init__(self):
        self.current_email: dict = {}
        self.current_task: int = 1
        self.step_count: int = 0
        self.last_reward: float = 0.0
        self.last_feedback: str = ""
        self.done: bool = False
        self.episode_scores = []
        self.task1_emails = [e for e in EMAIL_DATASET if e["task_id"] == 1]
        self.task2_emails = [e for e in EMAIL_DATASET if e["task_id"] == 2]
        self.task3_emails = [e for e in EMAIL_DATASET if e["task_id"] == 3]
    def reset(self, task_id: int = None) -> dict:
        if task_id is not None and task_id in (1, 2, 3):
            self.current_task = task_id
        else:
            self.current_task = random.choice([1, 2, 3])
        if self.current_task == 1:
            self.current_email = random.choice(self.task1_emails)
        elif self.current_task == 2:
            self.current_email = random.choice(self.task2_emails)
        else:
            self.current_email = random.choice(self.task3_emails)
        self.step_count = 0
        self.last_reward = 0.0
        self.last_feedback = ""
        self.done = False
        observation = EmailObservation(
            email_id=self.current_email["email_id"],
            sender=self.current_email["sender"],
            subject=self.current_email["subject"],
            body=self.current_email["body"],
            urgency_hint=self.current_email.get("urgency_hint"),
            task_id=self.current_email["task_id"],
            task_description=self.current_email["task_description"],
            done=False,
        )
        return {"observation": observation.model_dump()}
    def step(self, action: dict) -> dict:
        self.step_count += 1
        try:
            email_action = EmailAction(**action)
        except Exception as e:
            reward = EmailReward(
                score=0.0,
                category_score=0.0,
                priority_score=0.0,
                department_score=0.0,
                escalation_score=0.0,
                feedback=f"Invalid action format: {str(e)}",
            )
            self.done = True
            self.episode_scores.append(reward.score)
            if len(self.episode_scores) >= 3:
                avg = sum(self.episode_scores[-3:]) / 3
                if avg >= 0.8:
                    reward.score = min(1.0, reward.score + 0.05)
                    reward.feedback += " | +0.05 consistency bonus"
            self.last_reward = 0.0
            self.last_feedback = reward.feedback
            return {
                "observation": self._get_done_observation().model_dump(),
                "reward": reward.model_dump(),
                "done": True,
                "info": {"error": str(e)},
            }
        ground_truth = self.current_email["ground_truth"]
        if self.current_task == 1:
            reward = grade_task1(email_action, ground_truth)
        elif self.current_task == 2:
            reward = grade_task2(email_action, ground_truth)
        else:
            reward = grade_task3(email_action, ground_truth)
        self.last_reward = reward.score
        self.last_feedback = reward.feedback
        self.done = True
        done_observation = self._get_done_observation()
        return {
            "observation": done_observation.model_dump(),
            "reward": reward.model_dump(),
            "done": True,
            "info": {
                "task_id": self.current_task,
                "email_id": self.current_email["email_id"],
                "step": self.step_count,
            },
        }
    def state(self) -> dict:
        return {
            "current_task": self.current_task,
            "email_id": self.current_email.get("email_id", "none"),
            "step_count": self.step_count,
            "last_reward": self.last_reward,
            "last_feedback": self.last_feedback,
            "done": self.done,
        }
    def _get_done_observation(self) -> EmailObservation:
        return EmailObservation(
            email_id=self.current_email.get("email_id", "done"),
            sender="",
            subject="Episode complete",
            body="This episode has ended. Call reset() to start a new one.",
            urgency_hint=None,
            task_id=self.current_task,
            task_description="Episode complete.",
            done=True,
        )