"""Autonomous incident-response agents (N3).

One narrow loop, built to be read end to end:

    watcher  ->  coordinator  ->  maintenance agent  ->  action tools
             ->  action policy ->  verification       ->  run status

No agent framework: `coordinator.respond_to_escalation` is the workflow, the
state machine lives in `models.ALLOWED_TRANSITIONS`, and every model decision
is a validated Pydantic object rather than prose.
"""

from __future__ import annotations

from .coordinator import RunOptions, RunOutcome, evaluate_and_respond, respond_to_escalation
from .llm import (
                          AgentModel,
                          DeterministicAgentModel,
                          ModelInfo,
                          ModelMode,
                          OpenRouterAgentModel,
                          ScriptedAgentModel,
                          build_model,
)
from .models import (
                          ActionKind,
                          ActionPolicyDecision,
                          CheckResult,
                          MaintenanceAssessment,
                          RunStatus,
                          StepType,
                          VerificationResult,
                          WatcherEscalation,
)
from .watcher import evaluate_world as evaluate_world_for_escalations

__all__ = [
    "ActionKind",
    "ActionPolicyDecision",
    "AgentModel",
    "CheckResult",
    "DeterministicAgentModel",
    "MaintenanceAssessment",
    "ModelInfo",
    "ModelMode",
    "OpenRouterAgentModel",
    "RunOptions",
    "RunOutcome",
    "RunStatus",
    "ScriptedAgentModel",
    "StepType",
    "VerificationResult",
    "WatcherEscalation",
    "build_model",
    "evaluate_and_respond",
    "evaluate_world_for_escalations",
    "respond_to_escalation",
]
