from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, Field

AgentStatus = Literal[
    "completed",
    "completed_with_warnings",
    "failed",
    "cancelled",
    "waiting_human",
    "rejected",
    "scheduled",
    "published",
]


class AgentInput(BaseModel):
    topic_id: int
    channel_id: int
    topic_title: str
    channel_name: str
    channel_category: str
    channel_tone: str = ""
    forbidden_topics: list[str] = Field(default_factory=list)
    source_urls: list[str] = Field(default_factory=list)
    risk_threshold: float = 0.5
    channel_playbook: dict[str, Any] = Field(default_factory=dict)


class ResearchInput(AgentInput):
    topic_summary: str = ""
    topic_raw_text: str = ""


class ResearchOutput(BaseModel):
    status: AgentStatus = "completed"
    what_happened: str
    why_it_matters: str
    key_facts: list[str] = Field(default_factory=list)
    uncertainty: str = ""
    source_urls: list[str] = Field(default_factory=list)
    suggested_angles: list[str] = Field(default_factory=list)
    risk_notes: str = ""

    @property
    def source_links(self) -> list[str]:
        return self.source_urls

    @property
    def suggested_angle(self) -> str:
        return self.suggested_angles[0] if self.suggested_angles else ""


class FactcheckInput(AgentInput):
    research: ResearchOutput


class FactcheckOutput(BaseModel):
    status: AgentStatus = "completed"
    factcheck_result: Literal["pass", "pass_with_caution", "needs_human_review", "fail"] | None = None
    result: Literal["pass", "pass_with_caution", "needs_human_review", "fail"] = "pass"
    risk_score: float
    source_check: str = ""
    source_quality: str = ""
    source_date_if_available: str = ""
    unsupported_claims: list[str] = Field(default_factory=list)
    reason: str = ""
    risk_notes: str = ""
    human_review_required: bool | None = None
    requires_human_review: bool = False

    @property
    def decision(self) -> str:
        return self.result

    @property
    def supported_claims(self) -> bool:
        return not self.unsupported_claims

    @property
    def reliable_sources(self) -> bool:
        return bool(self.source_check.strip())

    @property
    def notes(self) -> str:
        return self.reason or self.risk_notes


class EditorInput(AgentInput):
    research: ResearchOutput
    factcheck: FactcheckOutput
    rewrite_notes: list[str] = Field(default_factory=list)
    post_length_limit: int = 1200


class EditorOutput(BaseModel):
    status: AgentStatus = "completed"
    title: str
    body: str
    visual_prompt: str = ""
    source_urls: list[str] = Field(default_factory=list)
    editorial_value: str = ""
    why_useful: str = ""
    required_structure_used: list[str] = Field(default_factory=list)
    channel_playbook_checklist: dict[str, bool] = Field(default_factory=dict)
    risk_notes: str = ""
    channel_fit_reason: str = ""
    tokens_input: int = 0
    tokens_output: int = 0
    estimated_cost: float = 0


class ChiefEditorInput(AgentInput):
    post_id: int | None = None
    draft: EditorOutput
    factcheck: FactcheckOutput
    rewrite_attempts_used: int = 0


class ChiefEditorOutput(BaseModel):
    status: AgentStatus = "completed"
    decision: Literal["approve", "approve_for_review", "rewrite_once", "reject", "waiting_human"]
    quality_score: float
    editorial_value_score: float = 0
    factuality_score: float = 0
    clarity_score: float = 0
    usefulness_score: float = 0
    channel_fit_score: float = 0
    originality_score: float = 0
    risk_score: float = 0
    overall_quality_score: float = 0
    reason: str = ""
    required_changes: list[str] = Field(default_factory=list)
    human_check_before_publication: list[str] = Field(default_factory=list)
    playbook_checklist: dict[str, bool] = Field(default_factory=dict)
    publish_safety: Literal["mock_only", "dry_run_review_required", "safe_for_future_manual_publish"] = "dry_run_review_required"
    checks: dict[str, bool] = Field(default_factory=dict)

    @property
    def issues(self) -> list[str]:
        return self.required_changes


@dataclass(frozen=True)
class AgentSpec:
    name: str
    task_type: str
    input_schema: type[BaseModel]
    output_schema: type[BaseModel]
    max_attempts: int
    timeout_seconds: int

    def metadata(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "task_type": self.task_type,
            "input_schema": self.input_schema.__name__,
            "output_schema": self.output_schema.__name__,
            "max_attempts": self.max_attempts,
            "timeout_seconds": self.timeout_seconds,
        }


RESEARCH_AGENT = AgentSpec(
    name="research_agent",
    task_type="research",
    input_schema=ResearchInput,
    output_schema=ResearchOutput,
    max_attempts=2,
    timeout_seconds=60,
)

FACTCHECK_AGENT = AgentSpec(
    name="factcheck_agent",
    task_type="fact_check",
    input_schema=FactcheckInput,
    output_schema=FactcheckOutput,
    max_attempts=1,
    timeout_seconds=45,
)

EDITOR_AGENT = AgentSpec(
    name="editor_agent",
    task_type="draft_generation",
    input_schema=EditorInput,
    output_schema=EditorOutput,
    max_attempts=2,
    timeout_seconds=90,
)

REWRITE_AGENT = AgentSpec(
    name="editor_agent",
    task_type="rewrite",
    input_schema=EditorInput,
    output_schema=EditorOutput,
    max_attempts=1,
    timeout_seconds=90,
)

CHIEF_EDITOR_AGENT = AgentSpec(
    name="chief_editor_agent",
    task_type="quality_control",
    input_schema=ChiefEditorInput,
    output_schema=ChiefEditorOutput,
    max_attempts=1,
    timeout_seconds=45,
)
