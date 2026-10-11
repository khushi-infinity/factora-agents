"""LLM provider abstraction — real OpenRouter model or a labelled stand-in.

Rules (N3):

  * the provider and model id come from the environment only
    (`OPENROUTER_API_KEY`, `FACTORA_LLM_MODEL`, default `openrouter/free`);
  * tests and the deterministic demo never touch the internet: they use
    `DeterministicAgentModel` (offline, evidence-driven) or `ScriptedAgentModel`
    (queued responses, used to inject malformed output);
  * the stand-ins are always reported as `DETERMINISTIC TEST MODEL` — the UI
    must never be able to present a fallback as a live AI model;
  * only the OpenRouter path imports `openai`, and only when it is used.
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ValidationError

from ..config import Settings, get_settings
from ..observability import get_observability
from .models import (
    InvestigationPlan,
    MaintenanceAssessment,
    MalformedOutputError,
    ProductionAssessment,
    SpecialistAssignment,
)

TASK_COORDINATOR_ASSIGNMENT = "coordinator_assignment"
TASK_INVESTIGATION_PLAN = "investigation_plan"
TASK_MAINTENANCE_ASSESSMENT = "maintenance_assessment"
TASK_PRODUCTION_ASSESSMENT = "production_assessment"      # N4
TASK_FINANCE_ASSESSMENT = "finance_assessment"            # N4

# Free OpenRouter models spend `max_tokens` on hidden reasoning too; leave room.
MAX_TOKENS = 6000
# Free tiers hand back empty completions under load; retry briefly, then fail
# loudly (the coordinator escalates rather than guessing).
PROVIDER_ATTEMPTS = 3
PROVIDER_BACKOFF_S = 1.0

REPAIR_INSTRUCTION = (
    "\n\nYour previous reply failed validation: {reason}\n"
    "Reply again with ONLY a short JSON object (no prose, no code fences, no "
    "more than ~15 lines), keeping every field inside the schema's limits."
)


class ModelMode(StrEnum):
    REAL = "REAL LLM"
    DETERMINISTIC = "DETERMINISTIC TEST MODEL"


@dataclass(frozen=True)
class ModelInfo:
    provider: str
    name: str
    mode: ModelMode
    detail: str = ""


@runtime_checkable
class AgentModel(Protocol):
    """The only surface the agents depend on."""

    info: ModelInfo

    def complete(self, *, system: str, user: str, task: str,
                 hints: dict[str, Any]) -> str:
        """Return the raw model text for one structured decision."""
        ...


# ── JSON extraction + structured completion ────────────────────────────────
_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def extract_json(text: str) -> str:
    """Pull the first JSON object out of a reply (tolerates fences/prose)."""
    fenced = _FENCE.search(text)
    if fenced:
        return fenced.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        return text[start:end + 1]
    return text.strip()


def complete_structured(
    model: AgentModel,
    schema: type[BaseModel],
    *,
    system: str,
    user: str,
    task: str,
    hints: dict[str, Any] | None = None,
    on_event: Callable[[str, dict[str, Any]], None] | None = None,
) -> BaseModel:
    """Complete one decision, repairing malformed output once before failing."""
    hints = hints or {}
    prompt = (
        f"{user}\n\nRespond with ONLY a JSON object matching this JSON Schema:\n"
        f"{json.dumps(schema.model_json_schema(), sort_keys=True)}\n"
        "Keep the object short: no prose, no extra keys, at most ~15 lines."
    )
    raw = model.complete(system=system, user=prompt, task=task, hints=hints)
    try:
        return schema.model_validate_json(extract_json(raw))
    except ValidationError as exc:
        if on_event:
            on_event("output_repair", {
                "task": task, "attempt": 1,
                "reason": _first_error(exc), "preview": raw[:200]})
        retry_prompt = (
            prompt
            + REPAIR_INSTRUCTION.format(reason=_first_error(exc))
            + f"\n\nStart of your previous reply:\n{raw[:200]}")
        raw = model.complete(system=system, user=retry_prompt, task=task, hints=hints)
        try:
            return schema.model_validate_json(extract_json(raw))
        except ValidationError as exc2:
            raise MalformedOutputError(
                f"{model.info.provider} output failed {schema.__name__} "
                f"validation twice: {_first_error(exc2)}") from exc2


def _first_error(exc: ValidationError) -> str:
    errors = exc.errors()
    if not errors:
        return "invalid payload"
    first = errors[0]
    return f"{'.'.join(str(loc) for loc in first['loc'])}: {first['msg']}"


# ── real provider: OpenRouter (OpenAI-compatible) ──────────────────────────
class OpenRouterAgentModel:
    """Primary N3 provider. Free-model alias by default; key from env only."""

    def __init__(self, settings: Settings | None = None) -> None:
        settings = settings or get_settings()
        if not settings.openrouter_api_key:
            raise ValueError("OPENROUTER_API_KEY is not configured")
        from openai import OpenAI  # imported lazily: optional dependency

        client = OpenAI(
            base_url=settings.openrouter_base_url,
            api_key=settings.openrouter_api_key,
            timeout=60.0,
        )
        observability = get_observability()
        if observability.initialized:
            import neatlogs

            client = neatlogs.wrap(client, workflow_name="factora.incident_response")
        self._client = client
        self._model = settings.factora_llm_model
        self.info = ModelInfo(
            provider="openrouter",
            name=settings.factora_llm_model,
            mode=ModelMode.REAL,
            detail="OpenRouter OpenAI-compatible chat completions",
        )

    def complete(self, *, system: str, user: str, task: str,
                 hints: dict[str, Any]) -> str:
        del hints  # the real model reads the prompt, not the hint dict
        last_error = "unknown"
        for attempt in range(1, PROVIDER_ATTEMPTS + 1):
            try:
                response = self._client.chat.completions.create(
                    model=self._model,
                    messages=[{"role": "system", "content": system},
                              {"role": "user", "content": user}],
                    temperature=0.1,
                    # Free OpenRouter models are often small reasoning models:
                    # reasoning tokens are spent from `max_tokens`, so leave
                    # headroom and ask OpenRouter to withhold the reasoning text.
                    max_tokens=MAX_TOKENS,
                    extra_body={"reasoning": {"enabled": False, "exclude": True}},
                )
                choice = (response.choices or [None])[0]
                content = ((choice.message.content or "").strip()
                           if choice is not None else "")
                if content:
                    return content
                last_error = f"empty completion (finish={getattr(choice, 'finish_reason', None)})"
            except Exception as exc:  # provider/network errors are transient
                last_error = f"{type(exc).__name__}: {exc}"
            if attempt < PROVIDER_ATTEMPTS:
                time.sleep(PROVIDER_BACKOFF_S * attempt)
        raise MalformedOutputError(
            f"openrouter returned no usable completion after "
            f"{PROVIDER_ATTEMPTS} attempts: {last_error}")


# ── offline stand-in: deterministic, evidence-driven, clearly labelled ─────
class DeterministicAgentModel:
    """Rule-based stand-in used when no OpenRouter key is configured.

    It is not a language model and never claims to be one (`mode` says
    `DETERMINISTIC TEST MODEL`). It does, however, read the *same tool results*
    the real model would see and derives its numbers from them, so the offline
    demo still rests on real factory evidence rather than a canned script.
    """

    info = ModelInfo(
        provider="deterministic",
        name="factora-deterministic-v1",
        mode=ModelMode.DETERMINISTIC,
        detail="offline rule-based stand-in (no network, no LLM)",
    )

    def complete(self, *, system: str, user: str, task: str,
                 hints: dict[str, Any]) -> str:
        del system, user
        if task == TASK_COORDINATOR_ASSIGNMENT:
            return _json(SpecialistAssignment(
                specialist="maintenance",
                goal=f"Resolve or contain "
                     f"{hints['incident']['incident_type'].lower().replace('_', ' ')} "
                     f"on {hints['machine']['machine_id']}",
                rationale=(
                    "The incident is a machine-condition fault; the maintenance "
                    "specialist owns condition evidence, spare parts and work "
                    "orders."),
            ))
        if task == TASK_PRODUCTION_ASSESSMENT:
            # The numbers are already deterministic; the stand-in simply echoes
            # the coordinator-computed pick inside the structured envelope.
            return _json(ProductionAssessment(
                paused_job_id=hints["tools"]["job_id"],
                remaining_quantity=hints["tools"]["remaining_qty"],
                recommended_candidate=hints["tools"]["recommended"],
                est_incremental_cost_usd=hints["tools"]["incremental_cost_usd"],
                expected_delay_hours=hints["tools"]["delay_hours"],
                operational_loss_if_idle_usd=float(
                    hints["tools"]["idle_cost_usd"] or 0.0),
                confidence="high" if hints["tools"]["recommended"] else "low",
                summary=(
                    f"Deterministic candidate comparison confirms "
                    f"{hints['tools']['recommended'] or 'WAIT'}: incremental "
                    f"cost {hints['tools']['incremental_cost_usd']} USD vs an "
                    f"idle cost of {hints['tools']['idle_cost_usd']} USD."),
            ))
        if task == TASK_FINANCE_ASSESSMENT:
            from .finance import _deterministic  # reuse the deterministic verdict

            payload = {
                "wait_cost_usd": hints["tools"]["wait_cost_usd"],
                "reroute_cost_usd": hints["tools"]["reroute_cost_usd"],
                "candidate": hints["tools"]["candidate"],
            }
            benefit = {
                "loss_avoided_usd": hints["tools"]["loss_avoided_usd"],
                "net_benefit_usd": hints["tools"]["net_benefit_usd"],
            }
            return _json(_deterministic(payload, benefit))
        if task == TASK_INVESTIGATION_PLAN:
            machine_id = hints["machine"]["machine_id"]
            incident_id = hints["incident"]["incident_id"]
            calls = [
                {"name": "get_machine", "args": {"machine_id": machine_id}},
                {"name": "get_recent_telemetry",
                 "args": {"machine_id": machine_id, "limit": 6}},
                {"name": "get_maintenance_history",
                 "args": {"machine_id": machine_id}},
                {"name": "get_open_work_orders", "args": {"machine_id": machine_id}},
                {"name": "get_current_production_job",
                 "args": {"machine_id": machine_id}},
                {"name": "get_active_incident", "args": {"incident_id": incident_id}},
            ]
            available = set(hints.get("read_tools") or [])
            return _json(InvestigationPlan(
                tool_calls=[call for call in calls
                            if not available or call["name"] in available],
                rationale="Collect condition, history, parts and production context "
                          "before recommending anything.",
            ))
        if task == TASK_MAINTENANCE_ASSESSMENT:
            return _json(_assess_from_evidence(hints))
        raise MalformedOutputError(f"deterministic model cannot serve task '{task}'")


def _json(model: BaseModel) -> str:
    return model.model_dump_json()


def _assess_from_evidence(hints: dict[str, Any]) -> MaintenanceAssessment:
    """Derive the assessment from the tool results the agent actually fetched."""
    tools: dict[str, dict[str, Any]] = hints.get("tools", {})
    machine_id = hints["machine"]["machine_id"]

    trend = (tools.get("get_recent_telemetry") or {}).get("trend", {})
    vib = trend.get("vibration_mm_s", {})
    temp = trend.get("bearing_temp_c", {})

    history = (tools.get("get_maintenance_history") or {}).get("events", [])
    bearing_events = [event for event in history
                      if "bearing" in (event.get("part_id") or "").lower()
                      or "bearing" in (event.get("issue") or "").lower()
                      or "bearing" in (event.get("action") or "").lower()]
    part_id = (bearing_events[-1].get("part_id") if bearing_events else None)

    part = (tools.get("get_spare_part") or {}).get("part") or {}
    orders = (tools.get("get_open_work_orders") or {}).get("work_orders", [])
    job = (tools.get("get_current_production_job") or {}).get("running")
    scheduled = min((order["scheduled_for"] for order in orders
                     if order.get("scheduled_for")), default=None)

    evidence = [
        f"vibration {vib.get('first')} -> {vib.get('last')} mm/s over "
        f"{trend.get('window_readings', 0)} readings",
        f"bearing temperature {temp.get('first')} -> {temp.get('last')} C",
        f"{len(bearing_events)} previous bearing-related maintenance event(s) on "
        f"{machine_id}",
    ]
    if part_id:
        evidence.append(
            f"{part_id} stock {part.get('stock_qty')} on hand "
            f"(reorder point {part.get('reorder_point')}, "
            f"lead time {part.get('lead_time_days')}d)")
    if scheduled:
        evidence.append(
            f"{len(orders)} open work order(s); earliest scheduled {scheduled}")
    if job:
        evidence.append(f"job {job['job_id']} is RUNNING on {machine_id}")

    return MaintenanceAssessment(
        probable_issue="Spindle bearing degradation",
        confidence="high" if len(bearing_events) >= 2 else "medium",
        evidence=evidence,
        risk_of_continued_operation="high",
        recommended_actions=["CREATE_URGENT_WORK_ORDER", "PLACE_IN_MAINTENANCE"],
        required_part_id=part_id,
        work_order={
            "issue": "Spindle bearing degradation (autonomous containment)",
            "proposed_action": "Replace spindle bearing and inspect the spindle "
                               "assembly before returning to service",
            "priority": "critical",
            "estimated_cost_usd": float(part.get("unit_cost_usd") or 0.0),
        },
        summary=(f"Evidence on {machine_id}: rising spindle vibration and bearing "
                 f"temperature, repeated prior bearing failures, and a scheduled "
                 f"work order that is later than the risk allows. Contain now and "
                 f"raise an urgent maintenance order."),
    )


# ── scripted model for tests / failure injection ───────────────────────────
class ScriptedAgentModel:
    """Returns queued replies in order — used to test repair and escalation."""

    info = ModelInfo(provider="scripted", name="scripted-test-model",
                     mode=ModelMode.DETERMINISTIC,
                     detail="test double with a fixed reply queue")

    def __init__(self, replies: list[str]) -> None:
        self._replies = list(replies)
        self.calls: list[str] = []

    def complete(self, *, system: str, user: str, task: str,
                 hints: dict[str, Any]) -> str:
        del system, user, hints
        self.calls.append(task)
        if not self._replies:
            raise MalformedOutputError("scripted model ran out of replies")
        return self._replies.pop(0)


def build_model(settings: Settings | None = None) -> AgentModel:
    """Real OpenRouter model when a key exists, otherwise the labelled stand-in."""
    settings = settings or get_settings()
    if settings.openrouter_api_key:
        try:
            return OpenRouterAgentModel(settings)
        except Exception as exc:  # pragma: no cover - defensive
            fallback = DeterministicAgentModel()
            return _DegradedModel(fallback, reason=f"{type(exc).__name__}: {exc}")
    return DeterministicAgentModel()


class _DegradedModel:
    """Wraps the stand-in when the real provider cannot be constructed."""

    def __init__(self, inner: AgentModel, reason: str) -> None:
        self._inner = inner
        self.info = ModelInfo(
            provider="openrouter-fallback", name=inner.info.name,
            mode=ModelMode.DETERMINISTIC,
            detail=f"OpenRouter unavailable, using deterministic stand-in ({reason})")

    def complete(self, *, system: str, user: str, task: str,
                 hints: dict[str, Any]) -> str:
        return self._inner.complete(system=system, user=user, task=task, hints=hints)
