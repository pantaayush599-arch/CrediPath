"""Database initialisation, idempotent seeding and demo reset."""

from __future__ import annotations

import csv
import io
from datetime import date

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

import os
import threading

from ..db import ASSETS_DIR, Base, SessionLocal, engine
from ..models import ActionProgress, Business
from ..scoring.record_schema import COLUMNS
from . import synthetic
from .assessment import run_assessment
from .csv_ingest import store_rows, validate_csv

SAMPLES_DIR = ASSETS_DIR / "samples"

_ready = False
_ready_lock = threading.Lock()


def init_db() -> None:
    Base.metadata.create_all(engine)


def ensure_ready() -> list[str]:
    """Create tables and seed the demo once per process.

    Called from the startup hook and again lazily on the first request, because
    serverless runtimes do not always run ASGI lifespan events.
    """
    global _ready
    if _ready:
        return []
    with _ready_lock:
        if _ready:
            return []
        init_db()
        created: list[str] = []
        if os.environ.get("CREDIPATH_AUTO_SEED", "1") != "0":
            with SessionLocal() as db:
                created = seed_demo(db)
        _ready = True
        return created


def records_to_csv(records: list[dict]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=COLUMNS, lineterminator="\n")
    w.writeheader()
    for r in records:
        w.writerow({c: "" if r.get(c) is None else r.get(c) for c in COLUMNS})
    return buf.getvalue()


def _validation_today() -> date:
    # Synthetic data runs to September 2026; never reject it because of a stale system clock.
    return max(date.today(), date(2026, 12, 31))


def seed_business(db: Session, seed: synthetic.BusinessSeed) -> Business:
    biz = Business(
        id=seed.id,
        name=seed.name,
        owner_name=seed.owner_name,
        category=seed.category,
        city=seed.city,
        years_in_operation=seed.years_in_operation,
        description=seed.description,
        bureau_status=seed.bureau_status,
        conventional_view=seed.conventional_view,
        is_synthetic=True,
        is_seeded=True,
    )
    db.add(biz)
    db.flush()
    # Seed data goes through the same validator and storage path as uploads.
    report = validate_csv(records_to_csv(seed.records).encode(), today=_validation_today())
    if report["error_count"]:
        raise RuntimeError(f"Seed data for {seed.id} failed validation: {report['errors'][:3]}")
    upload = store_rows(db, biz, report["rows"], f"{seed.id}-seed.csv", report, source="seed")
    for as_of in seed.history_as_of:
        run_assessment(db, biz, trigger="seed", upload_id=upload.id, as_of=as_of)
    run_assessment(db, biz, trigger="seed", upload_id=upload.id)
    return biz


def seed_demo(db: Session) -> list[str]:
    """Insert any missing demo businesses. Safe to run repeatedly."""
    created = []
    for seed in synthetic.all_businesses():
        if db.get(Business, seed.id) is not None:
            continue
        seed_business(db, seed)
        created.append(seed.id)
    # Demo progress for a business with history (not Raj, whose plan starts fresh).
    if "meena-general-store" in created:
        db.add(ActionProgress(business_id="meena-general-store", action_key="grow_income", status="in_progress"))
    db.commit()
    return created


def reset_demo(db: Session) -> list[str]:
    """Remove every business (seeded and user-created) and reseed the original demo."""
    for biz in db.scalars(select(Business)).all():
        db.delete(biz)
    db.flush()
    db.execute(delete(ActionProgress))
    db.commit()
    return seed_demo(db)


def write_sample_files() -> list[str]:
    """Write the downloadable sample CSVs (all synthetic)."""
    SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    raj, update = synthetic.raj_bakery()
    files = {
        "raj_bakery_update_sep2026.csv": records_to_csv(update),
        "raj_bakery_baseline.csv": records_to_csv(raj.records),
        "new_business_sample.csv": records_to_csv(synthetic.new_business_sample()),
        "credipath_template.csv": records_to_csv(synthetic.template_rows()),
        "invalid_example.csv": synthetic.invalid_example_csv(),
    }
    for name, text in files.items():
        (SAMPLES_DIR / name).write_text(text, encoding="utf-8")
    return sorted(files)


SAMPLE_DESCRIPTIONS = {
    "raj_bakery_update_sep2026.csv": "Raj's Bakery, September 2026: collected overdue invoices, backfilled sales and supplier records, new month of bank data. Upload to Raj's Bakery to reassess.",
    "new_business_sample.csv": "12 months of records for a new fictional business. Use with 'Add a business'.",
    "credipath_template.csv": "One example row of every record type, showing the expected columns.",
    "invalid_example.csv": "Deliberately broken rows to demonstrate validation errors and warnings.",
    "raj_bakery_baseline.csv": "The baseline records seeded for Raj's Bakery (for reference).",
}
