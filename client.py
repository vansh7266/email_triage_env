# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""Email Triage Env Environment Client."""

from typing import Dict

from openenv.core import EnvClient
from openenv.core.client_types import StepResult
from openenv.core.env_server.types import State

from .models import EmailAction, EmailObservation


class EmailTriageEnv(
    EnvClient[EmailAction, EmailObservation, State]
):
    """
    Client for the Email Triage RL Environment.

    This client maintains a persistent WebSocket connection to the environment server,
    enabling efficient multi-step interactions with lower latency.
    Each client instance has its own dedicated environment session on the server.

    Example:
        >>> # Connect to a running server
        >>> with EmailTriageEnv(base_url="http://localhost:8000") as client:
        ...     result = client.reset()
        ...     obs = result.observation
        ...     print(f"Email: {obs.subject}")
        ...
        ...     action = EmailAction(
        ...         category="billing",
        ...         priority="high",
        ...         department="finance",
        ...         escalate=False,
        ...         reasoning="Invoice issue detected"
        ...     )
        ...     result = client.step(action)
        ...     print(f"Score: {result.reward}")

    Example with Docker:
        >>> # Automatically start container and connect
        >>> client = EmailTriageEnv.from_docker_image("email_triage_env-env:latest")
        >>> try:
        ...     result = client.reset()
        ...     action = EmailAction(
        ...         category="billing",
        ...         priority="high",
        ...         department="finance",
        ...         escalate=False,
        ...         reasoning="Invoice issue detected"
        ...     )
        ...     result = client.step(action)
        ... finally:
        ...     client.close()
    """

    def _step_payload(self, action: EmailAction) -> Dict:
        """
        Convert EmailAction to JSON payload for step message.

        Args:
            action: EmailAction instance with category, priority,
                    department, escalate, and reasoning fields.

        Returns:
            Dictionary representation suitable for JSON encoding
        """
        return {
            "category": action.category,
            "priority": action.priority,
            "department": action.department,
            "escalate": action.escalate,
            "reasoning": action.reasoning,
        }

    def _parse_result(self, payload: Dict) -> StepResult[EmailObservation]:
        """
        Parse server response into StepResult[EmailObservation].

        Args:
            payload: JSON response data from server

        Returns:
            StepResult with EmailObservation
        """
        obs_data = payload.get("observation", {})
        observation = EmailObservation(
            email_id=obs_data.get("email_id", ""),
            sender=obs_data.get("sender", ""),
            subject=obs_data.get("subject", ""),
            body=obs_data.get("body", ""),
            urgency_hint=obs_data.get("urgency_hint"),
            task_id=obs_data.get("task_id", 1),
            task_description=obs_data.get("task_description", ""),
            done=obs_data.get("done", False),
        )

        return StepResult(
            observation=observation,
            reward=payload.get("reward"),
            done=payload.get("done", False),
        )

    def _parse_state(self, payload: Dict) -> State:
        """
        Parse server response into State object.

        Args:
            payload: JSON response from state request

        Returns:
            State object with episode_id and step_count
        """
        return State(
            episode_id=payload.get("episode_id"),
            step_count=payload.get("step_count", 0),
        )
