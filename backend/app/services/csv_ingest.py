"""CSV parsing, validation and storage.

Validation never invents values: a blank optional field stays blank (NULL in
the database) and is reported, so the scoring engine can count it against
data completeness instead of treating it as zero.
"""

from __future__ import annotations

import csv
import hashlib
import io
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Business, FinancialRecord, Upload, utcnow
from ..scoring.record_schema import (
    BANK_CATEGORIES,
    BASE_REQUIRED,
    COLUMNS,
    RECOMMENDED_BY_TYPE,
    RECORD_TYPES,
    REQUIRED_BY_TYPE,
)

MAX_BYTES = 5 * 1024 * 1024
MAX_ROWS = 50_000
MAX_LISTED_ISSUES = 200

TYPE_ALIASES = {
    "bank": "bank",
    "bank_txn": "bank",
    "bank_transaction": "bank",
    "upi": "bank",
    "sale": "sale",
    "sales": "sale",
    "invoice": "invoice",
    "invoices": "invoice",
    "supplier_payment": "supplier_payment",
    "supplier": "supplier_payment",
    "supplier_payments": "supplier_payment",
    "loan_repayment": "loan_repayment",
    "loan": "loan_repayment",
    "emi": "loan_repayment",
}
DIRECTION_ALIASES = {"credit": "credit", "cr": "credit", "in": "credit", "debit": "debit", "dr": "debit", "out": "debit"}
DATE_FORMATS = ["%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"]


class CSVFormatError(ValueError):
    pass


def _parse_date(v: str) -> date | None:
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(v, fmt).date()
        except ValueError:
            continue
    return None


def _parse_amount(v: str) -> float | None:
    cleaned = v.replace("₹", "").replace("Rs.", "").replace("INR", "").replace(",", "").replace(" ", "")
    try:
        return float(cleaned)
    except ValueError:
        return None


def validate_csv(content: bytes, today: date | None = None) -> dict:
    """Parse and validate a CSV file. Returns a report with normalised rows."""
    today = today or date.today()
    if len(content) == 0:
        raise CSVFormatError("The file is empty.")
    if len(content) > MAX_BYTES:
        raise CSVFormatError(f"File is larger than {MAX_BYTES // (1024 * 1024)} MB.")
    warnings: list[dict] = []
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("latin-1")
        warnings.append({"row": None, "field": None, "message": "File is not UTF-8; read as Latin-1. Check names for odd characters."})
    if "\x00" in text[:1024]:
        raise CSVFormatError("This does not look like a text CSV file.")
    reader = csv.reader(io.StringIO(text))
    try:
        header = next(reader)
    except StopIteration:
        raise CSVFormatError("The file is empty.")
    header = [h.strip().lower().replace(" ", "_") for h in header]
    missing_cols = [c for c in BASE_REQUIRED if c not in header]
    if missing_cols:
        raise CSVFormatError(
            f"Missing required column(s): {', '.join(missing_cols)}. Expected header: {','.join(COLUMNS)}"
        )
    unknown = [h for h in header if h and h not in COLUMNS]
    if unknown:
        warnings.append({"row": None, "field": None, "message": f"Ignored unknown column(s): {', '.join(unknown)}"})
    dup_cols = [c for c, n in Counter(header).items() if n > 1 and c]
    if dup_cols:
        raise CSVFormatError(f"Duplicate column(s): {', '.join(dup_cols)}")

    errors: list[dict] = []
    rows: list[dict] = []
    missing_recommended: dict[str, list[int]] = defaultdict(list)
    seen: Counter = Counter()
    possible_dupes: list[int] = []
    total = 0
    for line_no, raw in enumerate(reader, start=2):
        if not any(cell.strip() for cell in raw):
            continue
        total += 1
        if total > MAX_ROWS:
            raise CSVFormatError(f"More than {MAX_ROWS} rows; split the file.")
        if len(raw) > len(header):
            errors.append({"row": line_no, "field": None, "message": f"Row has {len(raw)} values but the header has {len(header)} columns."})
            continue
        raw = raw + [""] * (len(header) - len(raw))
        cells = {h: raw[i].strip() for i, h in enumerate(header) if h in COLUMNS}
        row_errors: list[dict] = []

        def err(field, msg):
            row_errors.append({"row": line_no, "field": field, "message": msg})

        rt_raw = cells.get("record_type", "").lower().replace(" ", "_")
        rt = TYPE_ALIASES.get(rt_raw)
        if not rt_raw:
            err("record_type", "record_type is required.")
        elif rt is None:
            err("record_type", f"Unknown record_type '{cells.get('record_type')}'. Use one of: {', '.join(RECORD_TYPES)}.")
        rec: dict = {c: None for c in COLUMNS}
        rec["record_type"] = rt
        for f in ("date", "due_date", "paid_date"):
            v = cells.get(f, "")
            if v:
                d = _parse_date(v)
                if d is None:
                    err(f, f"'{v}' is not a valid date (use YYYY-MM-DD).")
                elif d > today + timedelta(days=1) and f != "due_date":
                    err(f, f"{f} {d.isoformat()} is in the future.")
                elif d.year < 2000:
                    err(f, f"{f} {d.isoformat()} is implausibly old.")
                else:
                    rec[f] = d
            elif f == "date":
                err("date", "date is required.")
        amt_raw = cells.get("amount", "")
        if not amt_raw:
            err("amount", "amount is required.")
        else:
            amt = _parse_amount(amt_raw)
            if amt is None:
                err("amount", f"'{amt_raw}' is not a number.")
            elif amt <= 0:
                err("amount", "amount must be greater than zero (use direction=debit for money going out).")
            elif amt > 1e10:
                err("amount", "amount is implausibly large.")
            else:
                rec["amount"] = round(amt, 2)
        bal_raw = cells.get("balance_after", "")
        if bal_raw:
            bal = _parse_amount(bal_raw)
            if bal is None:
                err("balance_after", f"'{bal_raw}' is not a number.")
            else:
                rec["balance_after"] = round(bal, 2)
        for f in ("counterparty", "category", "channel", "reference", "notes"):
            v = cells.get(f, "")
            rec[f] = v[:160] if v else None
        dir_raw = cells.get("direction", "").lower()
        if dir_raw:
            if dir_raw in DIRECTION_ALIASES:
                rec["direction"] = DIRECTION_ALIASES[dir_raw]
            else:
                err("direction", f"direction must be credit or debit, got '{cells.get('direction')}'.")
        if rt:
            for f in REQUIRED_BY_TYPE[rt]:
                if rec.get(f) is None and not any(e["field"] == f for e in row_errors):
                    err(f, f"{f} is required for {rt} rows.")
            if rt != "bank" and rec["direction"] is not None:
                rec["direction"] = None  # only meaningful for bank rows
            if rt == "bank" and rec["category"]:
                rec["category"] = rec["category"].lower().replace(" ", "_")
                if rec["category"] not in BANK_CATEGORIES:
                    warnings.append({"row": line_no, "field": "category", "message": f"Unrecognised category '{rec['category']}' - treated as 'other'."})
                    rec["category"] = "other"
            if rt == "invoice" and rec["due_date"] and rec["date"] and rec["due_date"] < rec["date"]:
                err("due_date", "due_date is before the invoice date.")
            if rec["paid_date"] and rec["date"] and rec["paid_date"] < rec["date"] and rt in ("invoice", "supplier_payment"):
                warnings.append({"row": line_no, "field": "paid_date", "message": "paid_date is before the record date (advance payment?)."})
        if row_errors:
            errors.extend(row_errors)
            continue
        for f in RECOMMENDED_BY_TYPE[rt]:
            if rec.get(f) is None:
                missing_recommended[f"{rt}.{f}"].append(line_no)
        key = (rt, rec["date"], rec["amount"], rec["direction"], rec["counterparty"], rec["reference"])
        seen[key] += 1
        if seen[key] > 1:
            possible_dupes.append(line_no)
        rec["_occurrence"] = seen[key]
        rec["_line"] = line_no
        rows.append(rec)

    if total == 0:
        raise CSVFormatError("The file has a header but no data rows.")
    for field, lines in missing_recommended.items():
        warnings.append(
            {
                "row": None,
                "field": field,
                "message": f"{len(lines)} row(s) have no {field.split('.')[1]} (rows {', '.join(map(str, lines[:8]))}{'...' if len(lines) > 8 else ''}). "
                "Left blank, not zero; this lowers data completeness.",
            }
        )
    if possible_dupes:
        warnings.append({"row": None, "field": None, "message": f"{len(possible_dupes)} row(s) repeat an earlier row exactly (rows {', '.join(map(str, possible_dupes[:8]))}). Kept as separate entries; check they are genuine."})
    by_type = Counter(r["record_type"] for r in rows)
    dates = [r["date"] for r in rows]
    return {
        "rows_total": total,
        "rows_valid": len(rows),
        "rows_rejected": len({e["row"] for e in errors}),
        "errors": errors[:MAX_LISTED_ISSUES],
        "error_count": len(errors),
        "warnings": warnings[:MAX_LISTED_ISSUES],
        "warning_count": len(warnings),
        "by_type": dict(by_type),
        "date_range": [min(dates).isoformat(), max(dates).isoformat()] if dates else None,
        "rows": rows,
    }


def fingerprint(rec: dict) -> str:
    rt = rec["record_type"]
    if rt == "invoice" and rec.get("reference"):
        key = f"invoice|{rec['reference'].lower()}"
    elif rt == "loan_repayment":
        key = f"loan|{(rec.get('reference') or '').lower()}|{rec['date']}"
    else:
        key = "|".join(
            str(x)
            for x in (rt, rec["date"], f"{rec['amount']:.2f}", rec.get("direction"), (rec.get("counterparty") or "").lower(), rec.get("reference"), rec.get("_occurrence", 1))
        )
    return hashlib.sha256(key.encode()).hexdigest()[:40]


UPDATABLE = ["amount", "counterparty", "category", "channel", "due_date", "paid_date", "balance_after", "notes", "date", "direction"]


def store_rows(db: Session, business: Business, rows: list[dict], filename: str, report: dict, source: str = "csv") -> Upload:
    """Insert new rows; upsert invoices and loan instalments by reference."""
    upload = Upload(business_id=business.id, filename=filename, source=source, rows_total=report.get("rows_total", len(rows)), rows_rejected=report.get("rows_rejected", 0))
    db.add(upload)
    db.flush()
    existing = {
        r.fingerprint: r
        for r in db.scalars(select(FinancialRecord).where(FinancialRecord.business_id == business.id))
    }
    inserted = updated = duplicate = 0
    for rec in rows:
        fp = fingerprint(rec)
        clean = {k: v for k, v in rec.items() if not k.startswith("_")}
        if fp in existing:
            row = existing[fp]
            changes = {f: clean[f] for f in UPDATABLE if clean.get(f) is not None and getattr(row, f) != clean[f]}
            if changes and rec["record_type"] in ("invoice", "loan_repayment"):
                for f, v in changes.items():
                    setattr(row, f, v)
                row.updated_at = utcnow()
                row.upload_id = upload.id
                updated += 1
            else:
                duplicate += 1
            continue
        row = FinancialRecord(business_id=business.id, upload_id=upload.id, fingerprint=fp, **clean)
        db.add(row)
        existing[fp] = row
        inserted += 1
    upload.rows_inserted = inserted
    upload.rows_updated = updated
    upload.rows_duplicate = duplicate
    upload.report = {k: v for k, v in report.items() if k != "rows"}
    db.flush()
    return upload
