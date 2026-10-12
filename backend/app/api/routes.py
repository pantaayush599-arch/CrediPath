"""HTTP routes. Thin layer: validation and serialisation only; logic lives in services."""

from __future__ import annotations

import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import backend_label, get_session
from ..models import ActionProgress, Assessment, Business, Upload
from ..schemas import (
    AssessmentOut,
    BusinessCreate,
    BusinessOut,
    ProgressOut,
    ProgressUpdate,
    UploadResult,
    ValidationReport,
    WhatIfOut,
    WhatIfRequest,
)
from ..scoring.config import config_as_dict
from ..scoring.record_schema import COLUMNS, FIELD_HELP, RECOMMENDED_BY_TYPE, RECORD_TYPES, REQUIRED_BY_TYPE
from ..services import assessment as svc
from ..services.csv_ingest import CSVFormatError, MAX_BYTES, store_rows, validate_csv
from ..services.seed import SAMPLE_DESCRIPTIONS, SAMPLES_DIR, reset_demo
from ..scoring.recommend import ACTION_TO_INDICATOR

router = APIRouter(prefix="/api")


def _business(db: Session, business_id: str) -> Business:
    biz = db.get(Business, business_id)
    if biz is None:
        raise HTTPException(404, f"Business '{business_id}' not found")
    return biz


def _latest(db: Session, business_id: str) -> Assessment:
    a = svc.latest_assessment(db, business_id)
    if a is None:
        raise HTTPException(404, "No assessment yet. Upload records to create the first assessment.")
    return a


def _business_out(db: Session, biz: Business) -> dict:
    a = svc.latest_assessment(db, biz.id)
    count = db.scalar(select(func.count()).select_from(Assessment).where(Assessment.business_id == biz.id))
    avg_income = None
    if a is not None:
        vals = [m["inflow"] for m in a.monthly if m["inflow"] is not None]
        avg_income = round(sum(vals) / len(vals)) if vals else None
    return {
        "id": biz.id,
        "name": biz.name,
        "owner_name": biz.owner_name,
        "category": biz.category,
        "city": biz.city,
        "years_in_operation": biz.years_in_operation,
        "description": biz.description,
        "bureau_status": biz.bureau_status,
        "conventional_view": biz.conventional_view,
        "is_synthetic": biz.is_synthetic,
        "is_seeded": biz.is_seeded,
        "latest_score": a.overall_score if a else None,
        "latest_display_score": a.display_score if a else None,
        "confidence": a.confidence if a else None,
        "confidence_reasons": a.confidence_reasons if a else [],
        "confidence_checks": (a.summary or {}).get("confidence_checks", []) if a else [],
        "verification_count": sum(1 for f in a.flags if f.requires_verification) if a else 0,
        "flag_count": len(a.flags) if a else 0,
        "as_of_date": a.as_of_date.isoformat() if a else None,
        "assessment_count": count or 0,
        "avg_monthly_income": avg_income,
        "record_stats": svc.record_stats(db, biz.id),
    }


@router.get("/health")
def health():
    return {"status": "ok", "database": backend_label(), "data": "synthetic demonstration data"}


@router.get("/scoring/config")
def scoring_config():
    """Weights, thresholds and anomaly rules used by the rules engine."""
    return config_as_dict()


@router.get("/schema")
def record_schema():
    """CSV columns and per-type requirements."""
    return {
        "columns": COLUMNS,
        "record_types": RECORD_TYPES,
        "required": {"all": ["record_type", "date", "amount"], **REQUIRED_BY_TYPE},
        "recommended": RECOMMENDED_BY_TYPE,
        "help": FIELD_HELP,
        "max_file_mb": MAX_BYTES // (1024 * 1024),
    }


@router.get("/businesses", response_model=list[BusinessOut])
def list_businesses(db: Session = Depends(get_session)):
    """Portfolio list for the banker dashboard."""
    return [_business_out(db, b) for b in db.scalars(select(Business).order_by(Business.is_seeded.desc(), Business.created_at, Business.name))]


@router.post("/businesses", response_model=BusinessOut, status_code=201)
def create_business(body: BusinessCreate, db: Session = Depends(get_session)):
    """Onboard a new business profile. Records are added with a CSV upload."""
    slug = re.sub(r"[^a-z0-9]+", "-", body.name.lower()).strip("-")[:48] or "business"
    biz_id, n = slug, 2
    while db.get(Business, biz_id) is not None:
        biz_id, n = f"{slug}-{n}", n + 1
    biz = Business(
        id=biz_id,
        name=body.name.strip(),
        owner_name=body.owner_name.strip(),
        category=body.category.strip(),
        city=body.city.strip(),
        years_in_operation=body.years_in_operation,
        description=body.description.strip(),
        bureau_status="Not provided",
        conventional_view="No bureau information was shared for this demo profile.",
        is_synthetic=True,
        is_seeded=False,
        consent_given_at=datetime.now(timezone.utc),
    )
    db.add(biz)
    db.commit()
    return _business_out(db, biz)


@router.get("/businesses/{business_id}", response_model=BusinessOut)
def get_business(business_id: str, db: Session = Depends(get_session)):
    return _business_out(db, _business(db, business_id))


@router.get("/businesses/{business_id}/assessment", response_model=AssessmentOut)
def get_latest_assessment(business_id: str, db: Session = Depends(get_session)):
    """Latest assessment: score, indicators, explanations, flags and ranked recommendations."""
    _business(db, business_id)
    return svc.assessment_dict(db, _latest(db, business_id))


@router.get("/businesses/{business_id}/assessments")
def list_assessments(business_id: str, db: Session = Depends(get_session)):
    """Assessment history, newest first."""
    _business(db, business_id)
    rows = db.scalars(select(Assessment).where(Assessment.business_id == business_id).order_by(Assessment.id.desc())).all()
    return [svc.assessment_summary(a) for a in rows]


@router.get("/businesses/{business_id}/assessments/{assessment_id}", response_model=AssessmentOut)
def get_assessment(business_id: str, assessment_id: int, db: Session = Depends(get_session)):
    a = db.get(Assessment, assessment_id)
    if a is None or a.business_id != business_id:
        raise HTTPException(404, "Assessment not found")
    return svc.assessment_dict(db, a)


@router.get("/businesses/{business_id}/comparison")
def get_comparison(business_id: str, db: Session = Depends(get_session)):
    """Latest assessment compared with the one before it (null if only one exists)."""
    _business(db, business_id)
    cur = _latest(db, business_id)
    return svc.compare(svc.previous_assessment(db, cur), cur)


@router.post("/businesses/{business_id}/assess", response_model=AssessmentOut, status_code=201)
def reassess(business_id: str, db: Session = Depends(get_session)):
    """Recalculate from the stored records and save a new assessment."""
    biz = _business(db, business_id)
    try:
        a = svc.run_assessment(db, biz, trigger="manual")
    except ValueError as e:
        raise HTTPException(422, str(e))
    db.commit()
    return svc.assessment_dict(db, a)


@router.get("/businesses/{business_id}/explanations")
def explanations(business_id: str, db: Session = Depends(get_session)):
    """Indicator-level explanations and flags from the latest assessment."""
    _business(db, business_id)
    a = _latest(db, business_id)
    d = svc.assessment_dict(db, a)
    return {
        "assessment_id": a.id,
        "summary": d["summary"],
        "indicators": [{k: i[k] for k in ("key", "name", "sub_score", "band", "explanation_banker", "explanation_merchant")} for i in d["indicators"]],
        "flags": d["flags"],
    }


@router.get("/businesses/{business_id}/recommendations")
def recommendations(business_id: str, db: Session = Depends(get_session)):
    """Ranked improvement plan with the merchant's progress on each action."""
    _business(db, business_id)
    a = _latest(db, business_id)
    return {"assessment_id": a.id, "items": svc.assessment_dict(db, a)["recommendations"]}


@router.post("/businesses/{business_id}/what-if", response_model=WhatIfOut)
def what_if(business_id: str, body: WhatIfRequest, db: Session = Depends(get_session)):
    """Hypothetical score for selected actions. Never saved and never changes the assessment."""
    _business(db, business_id)
    a = _latest(db, business_id)
    return {"assessment_id": a.id, **svc.run_what_if(a, body.actions)}


@router.get("/businesses/{business_id}/progress", response_model=list[ProgressOut])
def get_progress(business_id: str, db: Session = Depends(get_session)):
    _business(db, business_id)
    return [
        {"action_key": p.action_key, "status": p.status, "note": p.note, "updated_at": p.updated_at.isoformat()}
        for p in svc.progress_map(db, business_id).values()
    ]


@router.put("/businesses/{business_id}/progress/{action_key}", response_model=ProgressOut)
def set_progress(business_id: str, action_key: str, body: ProgressUpdate, db: Session = Depends(get_session)):
    """Update progress on an action. Does not change the score."""
    _business(db, business_id)
    if action_key not in ACTION_TO_INDICATOR:
        raise HTTPException(404, f"Unknown action '{action_key}'")
    p = svc.progress_map(db, business_id).get(action_key)
    if p is None:
        p = ActionProgress(business_id=business_id, action_key=action_key)
        db.add(p)
    p.status = body.status
    p.note = body.note
    p.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"action_key": p.action_key, "status": p.status, "note": p.note, "updated_at": p.updated_at.isoformat()}


async def _read_upload(file: UploadFile) -> bytes:
    if file.filename and not file.filename.lower().endswith(".csv"):
        raise HTTPException(415, "Please upload a .csv file.")
    content = await file.read(MAX_BYTES + 1)
    return content


def _report_out(report: dict, filename: str) -> dict:
    out = {k: v for k, v in report.items() if k != "rows"}
    out["filename"] = filename
    out["can_import"] = report["rows_valid"] > 0
    return out


@router.post("/businesses/{business_id}/uploads/validate", response_model=ValidationReport)
async def validate_upload(business_id: str, file: UploadFile = File(...), db: Session = Depends(get_session)):
    """Validate a CSV without storing anything."""
    _business(db, business_id)
    content = await _read_upload(file)
    try:
        report = validate_csv(content)
    except CSVFormatError as e:
        raise HTTPException(422, str(e))
    return _report_out(report, file.filename or "upload.csv")


@router.post("/businesses/{business_id}/uploads", response_model=UploadResult, status_code=201)
async def upload(
    business_id: str,
    file: UploadFile = File(...),
    skip_invalid: bool = Query(False, description="Import valid rows even if some rows have errors"),
    db: Session = Depends(get_session),
):
    """Validate, store and reassess. Invoices and loan instalments are upserted by reference."""
    biz = _business(db, business_id)
    content = await _read_upload(file)
    filename = file.filename or "upload.csv"
    try:
        report = validate_csv(content)
    except CSVFormatError as e:
        raise HTTPException(422, str(e))
    rep_out = _report_out(report, filename)
    if report["error_count"] and not skip_invalid:
        raise HTTPException(422, {"message": f"{report['rows_rejected']} row(s) have errors. Fix them or import only the valid rows.", "validation": rep_out})
    if not report["rows"]:
        raise HTTPException(422, {"message": "No valid rows to import.", "validation": rep_out})
    prev = svc.latest_assessment(db, biz.id)
    up = store_rows(db, biz, report["rows"], filename, report)
    a = None
    comparison = None
    if up.rows_inserted or up.rows_updated or prev is None:
        a = svc.run_assessment(db, biz, trigger="upload", upload_id=up.id)
        comparison = svc.compare(prev, a)
        msg = f"Imported {up.rows_inserted} new and {up.rows_updated} updated row(s); business reassessed."
    else:
        msg = "Every row was already on file; nothing changed, so no reassessment was needed."
    db.commit()
    return {
        "upload_id": up.id,
        "filename": filename,
        "rows_inserted": up.rows_inserted,
        "rows_updated": up.rows_updated,
        "rows_duplicate": up.rows_duplicate,
        "rows_rejected": up.rows_rejected,
        "validation": rep_out,
        "assessment": svc.assessment_dict(db, a) if a else None,
        "comparison": comparison,
        "message": msg,
    }


@router.get("/businesses/{business_id}/uploads")
def list_uploads(business_id: str, db: Session = Depends(get_session)):
    _business(db, business_id)
    rows = db.scalars(select(Upload).where(Upload.business_id == business_id).order_by(Upload.id.desc())).all()
    return [
        {
            "id": u.id,
            "filename": u.filename,
            "source": u.source,
            "uploaded_at": u.uploaded_at.isoformat(),
            "rows_total": u.rows_total,
            "rows_inserted": u.rows_inserted,
            "rows_updated": u.rows_updated,
            "rows_duplicate": u.rows_duplicate,
            "rows_rejected": u.rows_rejected,
        }
        for u in rows
    ]


@router.get("/samples")
def list_samples():
    return [
        {"name": n, "description": d, "url": f"/api/samples/{n}"}
        for n, d in SAMPLE_DESCRIPTIONS.items()
        if (SAMPLES_DIR / n).exists()
    ]


@router.get("/samples/{name}")
def get_sample(name: str):
    if name not in SAMPLE_DESCRIPTIONS or not (SAMPLES_DIR / name).exists():
        raise HTTPException(404, "Sample not found")
    return FileResponse(SAMPLES_DIR / name, media_type="text/csv", filename=name)


@router.post("/demo/reset")
def demo_reset(confirm: bool = Query(False), db: Session = Depends(get_session)):
    """Delete all businesses, uploads, assessments and progress, then reseed the demo."""
    if not confirm:
        raise HTTPException(400, "Pass confirm=true to restore the demo data.")
    created = reset_demo(db)
    return {"restored": created, "message": "Demo data restored to its original state."}
