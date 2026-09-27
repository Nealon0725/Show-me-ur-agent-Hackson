"""Shared JSON-shaped contracts between evidence extraction and screening.

These types document the interface without changing the existing dictionary-based
runtime. Agent A and Agent B should review this module before either side depends
on newly added fields.
"""
from typing import Literal, NotRequired, TypedDict


EvidenceStatus = Literal["evidenced", "not_met", "unknown", "needs_review"]
RecommendationAction = Literal["SHORTLIST", "REQUEST_INFO", "HUMAN_REVIEW", "LOW_MATCH"]
WorkflowStatus = Literal[
    "CONFIRM_CRITERIA",
    "SCREENING",
    "REQUEST_INFO",
    "REQUEST_INFORMATION",  # Existing v1 name; migrate when Agent B updates workflow.py.
    "SHORTLIST_REVIEW",
    "LOW_MATCH_REVIEW",
    "HUMAN_REVIEW",
    "COMPLETE",
]


class EvidenceReference(TypedDict):
    source: str
    text: str
    line: int | None


class JobRequirement(TypedDict):
    id: str
    label: str
    description: str
    type: Literal["skill", "experience"]
    required: bool
    scored: bool
    weight: int
    source: str
    context: NotRequired[str | None]
    minimum_years: NotRequired[float]
    target_years: NotRequired[float]


class HumanReviewItem(TypedDict):
    id: str
    label: str
    source: str | None
    reason: str


class JobRequirements(TypedDict):
    role: str
    criteria: list[JobRequirement]
    raw_text: str
    human_review_items: list[HumanReviewItem]
    review_note: str


class CandidateEvidence(TypedDict):
    criterion_id: str
    status: EvidenceStatus
    weight: int
    reason: str
    evidence_refs: list[EvidenceReference]


class ModelUsage(TypedDict, total=False):
    input_tokens: int
    output_tokens: int
    total_tokens: int


class CandidateEvidenceProfile(TypedDict):
    candidate_id: str
    evidence: list[CandidateEvidence]
    parser: NotRequired[str]
    note: NotRequired[str]
    model_usage: NotRequired[ModelUsage]
    model_request_id: NotRequired[str | None]


class ScreeningScores(TypedDict):
    documented_score: int
    possible_score: int
    evidence_completeness: int


class FollowupQuestion(TypedDict):
    criterion_id: str
    question: str


class ScreeningResult(ScreeningScores):
    candidate_id: str
    criteria_version: int
    details: list[CandidateEvidence]
    strengths: list[str]
    gaps: list[str]
    missing_information: list[str]
    questions: list[FollowupQuestion]
    recommendation: str
    action: RecommendationAction
    rank: int | None
    rank_status: Literal["provisional", "final"]
    model_usage: ModelUsage
    model_request_id: str | None


class WorkflowEvent(TypedDict):
    step: int
    action: str
    detail: str


class WorkflowCandidate(TypedDict):
    id: str
    text: str
    answers: dict[str, dict[str, str]]
    round: int
    action: WorkflowStatus
    decision: dict[str, str] | None
    evaluation: NotRequired[ScreeningResult]


class WorkflowState(TypedDict):
    job: JobRequirements
    criteria_confirmed: bool
    events: list[WorkflowEvent]
    candidates: list[WorkflowCandidate]
