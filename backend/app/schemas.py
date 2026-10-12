"""Request and response schemas for the API."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class BusinessCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    owner_name: str = Field(min_length=2, max_length=160)
    category: str = Field(min_length=2, max_length=80)
    city: str = Field(min_length=2, max_length=120)
    years_in_operation: int | None = Field(default=None, ge=0, le=150)
    description: str = Field(default="", max_length=1000)
    consent: bool = Field(description="Owner consents to these records being used for this assessment")

    @field_validator("consent")
    @classmethod
    def must_consent(cls, v: bool) -> bool:
        if not v:
            raise ValueError("Consent is required before records can be assessed.")
        return v


class BusinessOut(BaseModel):
    id: str
    name: str
    owner_name: str
    category: str
    city: str
    years_in_operation: int | None
    description: str
    bureau_status: str
    conventional_view: str
    is_synthetic: bool
    is_seeded: bool
    latest_score: float | None = None
    latest_display_score: int | None = None
    confidence: str | None = None
    verification_count: int = 0
    flag_count: int = 0
    as_of_date: str | None = None
    assessment_count: int = 0
    avg_monthly_income: float | None = None
    record_stats: dict[str, Any] = {}


class Indicator(BaseModel):
    key: str
    name: str
    weight: float
    effective_weight: float
    sub_score: float | None
    contribution: float | None
    status: Literal["scored", "insufficient_data"]
    band: str
    metric: float | None
    metric_label: str
    benchmark: float
    explanation_banker: str
    explanation_merchant: str
    details: dict[str, Any]


class Flag(BaseModel):
    id: int
    kind: str
    category: str
    severity: Literal["info", "warning", "high"]
    title: str
    detail: str
    requires_verification: bool
    evidence: dict[str, Any]


class RecommendationOut(BaseModel):
    rank: int
    action_key: str
    indicator_key: str
    title: str
    short_label: str
    why: str
    steps: list[str]
    current_sub_score: float
    target_sub_score: float
    expected_impact: float
    in_top_plan: bool
    status: Literal["pending", "in_progress", "completed"]
    hypothetical: bool = True


class AssessmentOut(BaseModel):
    id: int
    created_at: str
    trigger: str
    upload_id: int | None
    as_of_date: str
    window_start: str
    window_end: str
    overall_score: float | None
    display_score: int | None
    confidence: str
    confidence_reasons: list[str]
    scoring_version: str
    record_count: int
    flag_count: int
    verification_count: int
    summary: dict[str, Any]
    indicators: list[Indicator]
    flags: list[Flag]
    recommendations: list[RecommendationOut]
    monthly: list[dict[str, Any]]
    disclaimer: str
    formula: str


class WhatIfRequest(BaseModel):
    actions: list[str] = Field(default_factory=list, description="action_key values from the improvement plan")


class WhatIfStep(BaseModel):
    action_key: str
    short_label: str
    title: str
    indicator_key: str
    current_sub_score: float
    target_sub_score: float
    delta: float


class WhatIfOut(BaseModel):
    hypothetical: Literal[True] = True
    assessment_id: int
    baseline_score: float | None
    baseline_display: int | None
    hypothetical_score: float | None
    hypothetical_display: int | None
    total_delta: float
    steps: list[WhatIfStep]
    ignored_actions: list[str]
    note: str


class ProgressUpdate(BaseModel):
    status: Literal["pending", "in_progress", "completed"]
    note: str | None = Field(default=None, max_length=500)


class ProgressOut(BaseModel):
    action_key: str
    status: str
    note: str | None
    updated_at: str
    message: str = "Progress saved. Your score changes only when updated records are uploaded and reassessed."


class ValidationIssue(BaseModel):
    row: int | None
    field: str | None
    message: str


class ValidationReport(BaseModel):
    filename: str
    rows_total: int
    rows_valid: int
    rows_rejected: int
    error_count: int
    warning_count: int
    errors: list[ValidationIssue]
    warnings: list[ValidationIssue]
    by_type: dict[str, int]
    date_range: list[str] | None
    can_import: bool


class UploadResult(BaseModel):
    upload_id: int
    filename: str
    rows_inserted: int
    rows_updated: int
    rows_duplicate: int
    rows_rejected: int
    validation: ValidationReport
    assessment: AssessmentOut | None
    comparison: dict[str, Any] | None
    message: str
