from pydantic import BaseModel, Field
from typing import Optional
class EmailObservation(BaseModel):
    email_id: str = Field(description="Unique identifier for this email")
    sender: str = Field(description="Email address of the sender")
    subject: str = Field(description="Subject line of the email")
    body: str = Field(description="Full body content of the email")
    urgency_hint: Optional[str] = Field(
        default=None,
        description="Optional urgency hint: low, medium, or high"
    )
    task_id: int = Field(description="Current task number: 1 (easy), 2 (medium), 3 (hard)")
    task_description: str = Field(description="Instructions for what the agent must do")
    done: bool = Field(default=False, description="True if this episode is complete")
class EmailAction(BaseModel):
    category: str = Field(
        description="Category: billing | technical_support | complaint | general_inquiry | spam"
    )
    priority: str = Field(
        description="Priority level: low | medium | high"
    )
    department: str = Field(
        description="Department to route to: finance | engineering | customer_success | sales | security"
    )
    escalate: bool = Field(
        description="True if this email needs immediate human escalation"
    )
    reasoning: str = Field(
        description="Brief explanation of why the agent made this decision"
    )
class EmailReward(BaseModel):
    score: float = Field(
        ge=0.0, le=1.0,
        description="Total reward score between 0.0 and 1.0"
    )
    category_score: float = Field(
        ge=0.0, le=1.0,
        description="Score for correct category (0.0 or 1.0)"
    )
    priority_score: float = Field(
        ge=0.0, le=1.0,
        description="Score for correct priority (0.0 or 1.0)"
    )
    department_score: float = Field(
        ge=0.0, le=1.0,
        description="Score for correct department routing"
    )
    escalation_score: float = Field(
        ge=0.0, le=1.0,
        description="Score for correct escalation decision"
    )
    feedback: str = Field(
        description="Explanation of what was right or wrong"
    )