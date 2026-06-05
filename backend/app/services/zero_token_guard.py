from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.all_models import AgentRun, CostEvent


ZERO_TOKEN_STEPS = (
    "source_fetch",
    "rss_parse",
    "article_extract",
    "dedupe",
    "freshness_score",
    "topic_score",
    "radar",
    "candidate_collect",
    "media_preview",
    "max_packaging",
)


@dataclass(frozen=True)
class ZeroTokenSnapshot:
    agent_runs: int
    cost_events: int
    tokens_input: int
    tokens_output: int
    estimated_cost: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "agent_runs": self.agent_runs,
            "cost_events": self.cost_events,
            "tokens_input": self.tokens_input,
            "tokens_output": self.tokens_output,
            "estimated_cost": round(float(self.estimated_cost or 0), 8),
        }


def zero_token_snapshot(db: Session) -> ZeroTokenSnapshot:
    return ZeroTokenSnapshot(
        agent_runs=int(db.scalar(select(func.count()).select_from(AgentRun)) or 0),
        cost_events=int(db.scalar(select(func.count()).select_from(CostEvent)) or 0),
        tokens_input=int(db.scalar(select(func.coalesce(func.sum(CostEvent.tokens_input), 0))) or 0),
        tokens_output=int(db.scalar(select(func.coalesce(func.sum(CostEvent.tokens_output), 0))) or 0),
        estimated_cost=float(db.scalar(select(func.coalesce(func.sum(CostEvent.estimated_cost), 0.0))) or 0.0),
    )


def zero_token_delta(before: ZeroTokenSnapshot, after: ZeroTokenSnapshot) -> dict[str, Any]:
    return {
        "agent_runs": after.agent_runs - before.agent_runs,
        "cost_events": after.cost_events - before.cost_events,
        "tokens_input": after.tokens_input - before.tokens_input,
        "tokens_output": after.tokens_output - before.tokens_output,
        "estimated_cost": round(after.estimated_cost - before.estimated_cost, 8),
    }


def assert_zero_token_delta(before: ZeroTokenSnapshot, after: ZeroTokenSnapshot, *, step: str) -> None:
    delta = zero_token_delta(before, after)
    if any(
        [
            delta["agent_runs"] != 0,
            delta["cost_events"] != 0,
            delta["tokens_input"] != 0,
            delta["tokens_output"] != 0,
            abs(float(delta["estimated_cost"])) > 0.0000001,
        ]
    ):
        raise AssertionError(f"{step} is not zero-token: {delta}")


def zero_token_metadata(**extra: Any) -> dict[str, Any]:
    return {
        "zero_token": True,
        "llm_calls": 0,
        "tokens_input": 0,
        "tokens_output": 0,
        "cost_usd": 0.0,
        "zero_token_steps": list(ZERO_TOKEN_STEPS),
        **extra,
    }
