"""ORM models: businesses, their records, uploads, assessments and plan progress."""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Business(Base):
    __tablename__ = "businesses"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    owner_name: Mapped[str] = mapped_column(String(160))
    category: Mapped[str] = mapped_column(String(80))
    city: Mapped[str] = mapped_column(String(120))
    years_in_operation: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str] = mapped_column(Text, default="")
    bureau_status: Mapped[str] = mapped_column(String(60), default="Unknown")
    conventional_view: Mapped[str] = mapped_column(Text, default="")
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=True)
    is_seeded: Mapped[bool] = mapped_column(Boolean, default=False)
    consent_given_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    records: Mapped[list["FinancialRecord"]] = relationship(back_populates="business", cascade="all, delete-orphan", passive_deletes=True)
    assessments: Mapped[list["Assessment"]] = relationship(back_populates="business", cascade="all, delete-orphan", passive_deletes=True, order_by="Assessment.id")
    uploads: Mapped[list["Upload"]] = relationship(back_populates="business", cascade="all, delete-orphan", passive_deletes=True)
    progress: Mapped[list["ActionProgress"]] = relationship(back_populates="business", cascade="all, delete-orphan", passive_deletes=True)


class Upload(Base):
    __tablename__ = "uploads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    source: Mapped[str] = mapped_column(String(20), default="csv")  # csv | seed
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    rows_total: Mapped[int] = mapped_column(Integer, default=0)
    rows_inserted: Mapped[int] = mapped_column(Integer, default=0)
    rows_updated: Mapped[int] = mapped_column(Integer, default=0)
    rows_duplicate: Mapped[int] = mapped_column(Integer, default=0)
    rows_rejected: Mapped[int] = mapped_column(Integer, default=0)
    report: Mapped[dict] = mapped_column(JSON, default=dict)

    business: Mapped[Business] = relationship(back_populates="uploads")


class FinancialRecord(Base):
    __tablename__ = "financial_records"
    __table_args__ = (
        UniqueConstraint("business_id", "fingerprint", name="uq_record_fingerprint"),
        Index("ix_records_business_type_date", "business_id", "record_type", "date"),
        CheckConstraint("amount > 0", name="ck_amount_positive"),
        CheckConstraint(
            "record_type IN ('bank','sale','invoice','supplier_payment','loan_repayment')",
            name="ck_record_type",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"))
    upload_id: Mapped[int | None] = mapped_column(ForeignKey("uploads.id", ondelete="SET NULL"), nullable=True)
    record_type: Mapped[str] = mapped_column(String(20))
    date: Mapped[date] = mapped_column(Date)
    amount: Mapped[float] = mapped_column(Float)
    direction: Mapped[str | None] = mapped_column(String(10), nullable=True)
    counterparty: Mapped[str | None] = mapped_column(String(160), nullable=True)
    category: Mapped[str | None] = mapped_column(String(40), nullable=True)
    channel: Mapped[str | None] = mapped_column(String(40), nullable=True)
    reference: Mapped[str | None] = mapped_column(String(80), nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    paid_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    balance_after: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Identity used for de-duplication / upsert (invoice & loan rows by reference).
    fingerprint: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    business: Mapped[Business] = relationship(back_populates="records")


class Assessment(Base):
    __tablename__ = "assessments"
    __table_args__ = (Index("ix_assessments_business_created", "business_id", "id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    trigger: Mapped[str] = mapped_column(String(20))  # seed | upload | manual
    upload_id: Mapped[int | None] = mapped_column(ForeignKey("uploads.id", ondelete="SET NULL"), nullable=True)
    scoring_version: Mapped[str] = mapped_column(String(20))
    as_of_date: Mapped[date] = mapped_column(Date)
    window_start: Mapped[date] = mapped_column(Date)
    window_end: Mapped[date] = mapped_column(Date)
    overall_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    display_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    confidence: Mapped[str] = mapped_column(String(10))
    confidence_reasons: Mapped[list] = mapped_column(JSON, default=list)
    record_count: Mapped[int] = mapped_column(Integer, default=0)
    summary: Mapped[dict] = mapped_column(JSON, default=dict)  # explanations
    monthly: Mapped[list] = mapped_column(JSON, default=list)  # monthly series used by charts

    business: Mapped[Business] = relationship(back_populates="assessments")
    indicators: Mapped[list["IndicatorScore"]] = relationship(back_populates="assessment", cascade="all, delete-orphan", passive_deletes=True, order_by="IndicatorScore.position")
    flags: Mapped[list["RiskFlag"]] = relationship(back_populates="assessment", cascade="all, delete-orphan", passive_deletes=True, order_by="RiskFlag.id")
    recommendations: Mapped[list["Recommendation"]] = relationship(back_populates="assessment", cascade="all, delete-orphan", passive_deletes=True, order_by="Recommendation.rank")


class IndicatorScore(Base):
    __tablename__ = "indicator_scores"
    __table_args__ = (
        UniqueConstraint("assessment_id", "key", name="uq_indicator_per_assessment"),
        CheckConstraint("sub_score IS NULL OR (sub_score >= 0 AND sub_score <= 100)", name="ck_sub_score_range"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    assessment_id: Mapped[int] = mapped_column(ForeignKey("assessments.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    key: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(80))
    weight: Mapped[float] = mapped_column(Float)
    effective_weight: Mapped[float] = mapped_column(Float)
    sub_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    contribution: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(20))
    band: Mapped[str] = mapped_column(String(20))
    metric: Mapped[float | None] = mapped_column(Float, nullable=True)
    metric_label: Mapped[str] = mapped_column(String(160))
    benchmark: Mapped[float] = mapped_column(Float)
    explanation_banker: Mapped[str] = mapped_column(Text, default="")
    explanation_merchant: Mapped[str] = mapped_column(Text, default="")
    details: Mapped[dict] = mapped_column(JSON, default=dict)

    assessment: Mapped[Assessment] = relationship(back_populates="indicators")


class RiskFlag(Base):
    __tablename__ = "risk_flags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    assessment_id: Mapped[int] = mapped_column(ForeignKey("assessments.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(40))
    category: Mapped[str] = mapped_column(String(20))
    severity: Mapped[str] = mapped_column(String(10))
    title: Mapped[str] = mapped_column(String(200))
    detail: Mapped[str] = mapped_column(Text)
    requires_verification: Mapped[bool] = mapped_column(Boolean, default=False)
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)

    assessment: Mapped[Assessment] = relationship(back_populates="flags")


class Recommendation(Base):
    __tablename__ = "recommendations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    assessment_id: Mapped[int] = mapped_column(ForeignKey("assessments.id", ondelete="CASCADE"), index=True)
    rank: Mapped[int] = mapped_column(Integer)
    action_key: Mapped[str] = mapped_column(String(40))
    indicator_key: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(120))
    short_label: Mapped[str] = mapped_column(String(30))
    why: Mapped[str] = mapped_column(Text)
    steps: Mapped[list] = mapped_column(JSON, default=list)
    current_sub_score: Mapped[float] = mapped_column(Float)
    target_sub_score: Mapped[float] = mapped_column(Float)
    expected_impact: Mapped[float] = mapped_column(Float)
    in_top_plan: Mapped[bool] = mapped_column(Boolean, default=False)

    assessment: Mapped[Assessment] = relationship(back_populates="recommendations")


class ActionProgress(Base):
    """Merchant's progress on an improvement action. Never changes the score."""

    __tablename__ = "action_progress"
    __table_args__ = (
        UniqueConstraint("business_id", "action_key", name="uq_progress_action"),
        CheckConstraint("status IN ('pending','in_progress','completed')", name="ck_progress_status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    action_key: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    business: Mapped[Business] = relationship(back_populates="progress")


class User(Base):
    """Demo sign-in account. Bankers see every applicant; a merchant sees only their business."""

    __tablename__ = "users"
    __table_args__ = (CheckConstraint("role IN ('banker','merchant')", name="ck_user_role"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(10))
    display_name: Mapped[str] = mapped_column(String(160))
    organisation: Mapped[str] = mapped_column(String(160), default="")
    business_id: Mapped[str | None] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), nullable=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
