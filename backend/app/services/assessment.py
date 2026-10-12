"""Assessment service: run the engine on stored records and persist the result.

Both dashboards read assessments produced here; there is no other path to a
score.
"""

from __future__ import annotations

import math
from datetime import date

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import ActionProgress, Assessment, Business, FinancialRecord, IndicatorScore, Recommendation, RiskFlag
from ..scoring import config as C
from ..scoring.engine import score_records, to_frame
from ..scoring.explain import DISCLAIMER, indicator_text, summaries
from ..scoring.quality import run_checks
from ..scoring.recommend import build_plan, what_if
from ..scoring.record_schema import COLUMNS

RECORD_FIELDS = ["id"] + COLUMNS


def load_records(db: Session, business_id: str) -> list[dict]:
    rows = db.scalars(
        select(FinancialRecord).where(FinancialRecord.business_id == business_id).order_by(FinancialRecord.date, FinancialRecord.id)
    ).all()
    return [{f: getattr(r, f) for f in RECORD_FIELDS} for r in rows]


def _clean(v):
    if v is None:
        return None
    if isinstance(v, float) and math.isnan(v):
        return None
    if hasattr(v, "item"):
        v = v.item()
        if isinstance(v, float) and math.isnan(v):
            return None
    return v


def _monthly_rows(ms: pd.DataFrame) -> list[dict]:
    out = []
    for m, r in ms.iterrows():
        out.append(
            {
                "month": str(m),
                "has_bank": bool(r.has_bank),
                "inflow": _clean(r.inflow),
                "outflow": _clean(r.outflow),
                "net": _clean(r.net),
                "month_end_balance": _clean(r.month_end_balance),
                "sales_register": _clean(r.sales_register),
                "other_credit": _clean(r.other_credit),
            }
        )
    return out


def _jsonable(obj):
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, (pd.Timestamp, date)):
        return obj.isoformat()[:10]
    return _clean(obj)


def run_assessment(db: Session, business: Business, trigger: str, upload_id: int | None = None, as_of: str | None = None) -> Assessment:
    records = load_records(db, business.id)
    if not records:
        raise ValueError("This business has no records yet. Upload a CSV to create its first assessment.")
    df = to_frame(records)
    result = score_records(df, pd.Timestamp(as_of) if as_of else None)
    flags = run_checks(df, result["window"], result["monthly"], result["indicators"], result["confidence"])
    summary = summaries(result)
    plan = build_plan(result["indicators"])
    a = Assessment(
        business_id=business.id,
        trigger=trigger,
        upload_id=upload_id,
        scoring_version=C.SCORING_VERSION,
        as_of_date=date.fromisoformat(result["as_of"]),
        window_start=date.fromisoformat(result["window_start"]),
        window_end=date.fromisoformat(result["window_end"]),
        overall_score=result["overall_score"],
        display_score=result["display_score"],
        confidence=result["confidence"]["level"],
        confidence_reasons=result["confidence"]["reasons"],
        record_count=int((df.date <= result["window"].as_of).sum()),
        summary=_jsonable({**summary, "confidence_checks": result["confidence"]["checks"]}),
        monthly=_monthly_rows(result["monthly"]),
    )
    for pos, ind in enumerate(result["indicators"]):
        text = indicator_text(ind)
        a.indicators.append(
            IndicatorScore(
                position=pos,
                key=ind["key"],
                name=ind["name"],
                weight=ind["weight"],
                effective_weight=ind["effective_weight"],
                sub_score=ind["sub_score"],
                contribution=ind["contribution"],
                status=ind["status"],
                band=ind["band"],
                metric=_clean(ind["metric"]),
                metric_label=ind["metric_label"],
                benchmark=ind["benchmark"],
                explanation_banker=text["banker"],
                explanation_merchant=text["merchant"],
                details=_jsonable(ind["details"] | ({"reason": ind["reason"]} if ind["reason"] else {})),
            )
        )
    for f in flags:
        a.flags.append(RiskFlag(**{k: _jsonable(v) if k == "evidence" else v for k, v in f.items()}))
    for p in plan:
        a.recommendations.append(
            Recommendation(**{k: p[k] for k in ("rank", "action_key", "indicator_key", "title", "short_label", "why", "steps", "current_sub_score", "target_sub_score", "expected_impact", "in_top_plan")})
        )
    db.add(a)
    db.flush()
    return a


def latest_assessment(db: Session, business_id: str) -> Assessment | None:
    return db.scalars(select(Assessment).where(Assessment.business_id == business_id).order_by(Assessment.id.desc()).limit(1)).first()


def previous_assessment(db: Session, a: Assessment) -> Assessment | None:
    return db.scalars(
        select(Assessment).where(Assessment.business_id == a.business_id, Assessment.id < a.id).order_by(Assessment.id.desc()).limit(1)
    ).first()


def indicator_dict(i: IndicatorScore) -> dict:
    return {
        "key": i.key,
        "name": i.name,
        "weight": i.weight,
        "effective_weight": i.effective_weight,
        "sub_score": i.sub_score,
        "contribution": i.contribution,
        "status": i.status,
        "band": i.band,
        "metric": i.metric,
        "metric_label": i.metric_label,
        "benchmark": i.benchmark,
        "explanation_banker": i.explanation_banker,
        "explanation_merchant": i.explanation_merchant,
        "details": i.details,
    }


def flag_dict(f: RiskFlag) -> dict:
    return {
        "id": f.id,
        "kind": f.kind,
        "category": f.category,
        "severity": f.severity,
        "title": f.title,
        "detail": f.detail,
        "requires_verification": f.requires_verification,
        "evidence": f.evidence,
    }


def rec_dict(r: Recommendation, status: str | None = None) -> dict:
    return {
        "rank": r.rank,
        "action_key": r.action_key,
        "indicator_key": r.indicator_key,
        "title": r.title,
        "short_label": r.short_label,
        "why": r.why,
        "steps": r.steps,
        "current_sub_score": r.current_sub_score,
        "target_sub_score": r.target_sub_score,
        "expected_impact": r.expected_impact,
        "in_top_plan": r.in_top_plan,
        "status": status or "pending",
        "hypothetical": True,
    }


def assessment_summary(a: Assessment) -> dict:
    return {
        "id": a.id,
        "created_at": a.created_at.isoformat(),
        "trigger": a.trigger,
        "upload_id": a.upload_id,
        "as_of_date": a.as_of_date.isoformat(),
        "window_start": a.window_start.isoformat(),
        "window_end": a.window_end.isoformat(),
        "overall_score": a.overall_score,
        "display_score": a.display_score,
        "confidence": a.confidence,
        "scoring_version": a.scoring_version,
        "flag_count": len(a.flags),
        "verification_count": sum(1 for f in a.flags if f.requires_verification),
        "indicators": {i.key: i.sub_score for i in a.indicators},
    }


def progress_map(db: Session, business_id: str) -> dict[str, ActionProgress]:
    return {p.action_key: p for p in db.scalars(select(ActionProgress).where(ActionProgress.business_id == business_id))}


def assessment_dict(db: Session, a: Assessment) -> dict:
    prog = progress_map(db, a.business_id)
    return {
        **assessment_summary(a),
        "confidence_reasons": a.confidence_reasons,
        "record_count": a.record_count,
        "summary": a.summary,
        "indicators": [indicator_dict(i) for i in a.indicators],
        "flags": [flag_dict(f) for f in a.flags],
        "recommendations": [rec_dict(r, prog[r.action_key].status if r.action_key in prog else None) for r in a.recommendations],
        "monthly": a.monthly,
        "disclaimer": DISCLAIMER,
        "formula": "Overall = sum(sub-score x weight)",
    }


def compare(prev: Assessment | None, cur: Assessment) -> dict | None:
    if prev is None:
        return None
    p_ind = {i.key: i for i in prev.indicators}
    rows = []
    for i in cur.indicators:
        before = p_ind.get(i.key)
        b = before.sub_score if before else None
        rows.append(
            {
                "key": i.key,
                "name": i.name,
                "before": b,
                "after": i.sub_score,
                "delta": round(i.sub_score - b, 2) if (b is not None and i.sub_score is not None) else None,
            }
        )
    p_titles = [f.title for f in prev.flags]
    c_titles = [f.title for f in cur.flags]
    return {
        "previous": assessment_summary(prev),
        "current": assessment_summary(cur),
        "score_delta": round((cur.overall_score or 0) - (prev.overall_score or 0), 2),
        "indicators": rows,
        "flags_resolved": [t for t in p_titles if t not in c_titles],
        "flags_new": [t for t in c_titles if t not in p_titles],
        "flags_before": len(prev.flags),
        "flags_after": len(cur.flags),
    }


def run_what_if(a: Assessment, actions: list[str]) -> dict:
    inds = [indicator_dict(i) for i in a.indicators]
    plan = [rec_dict(r) for r in a.recommendations]
    return what_if(inds, plan, actions)


def record_stats(db: Session, business_id: str) -> dict:
    rows = db.execute(
        select(FinancialRecord.record_type, func.count(), func.min(FinancialRecord.date), func.max(FinancialRecord.date))
        .where(FinancialRecord.business_id == business_id)
        .group_by(FinancialRecord.record_type)
    ).all()
    return {rt: {"count": n, "first": lo.isoformat(), "last": hi.isoformat()} for rt, n, lo, hi in rows}
