"""Deterministic, explainable rules engine.

Pipeline: records -> pandas frame -> eight raw metrics -> 0-100 sub-scores
-> weighted overall score. ``compute_overall`` is the single function that
turns sub-scores into a score; the assessment, the what-if simulator and the
tests all go through it.

Missing information is never scored as zero: an indicator without enough
evidence is marked ``insufficient_data`` and excluded, and the remaining
weights are re-normalised. The gap itself is penalised only through the
data-completeness indicator and surfaced as a flag.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Iterable

import numpy as np
import pandas as pd

from . import config as C
from .record_schema import COLUMNS, RECOMMENDED_BY_TYPE

STRING_COLS = ["record_type", "direction", "counterparty", "category", "channel", "reference", "notes"]


def round_half_up(x: float, ndigits: int = 0) -> float:
    q = 10**ndigits
    return math.floor(x * q + 0.5) / q


def to_frame(records: Iterable[dict]) -> pd.DataFrame:
    """Normalise record dicts (from the DB or a CSV) into a typed frame."""
    df = pd.DataFrame(list(records))
    for col in COLUMNS:
        if col not in df.columns:
            df[col] = None
    if "id" not in df.columns:
        df["id"] = range(len(df))
    df = df.astype({c: "object" for c in STRING_COLS})
    for col in STRING_COLS:
        df[col] = df[col].map(lambda v: None if v is None or (isinstance(v, float) and math.isnan(v)) or str(v).strip() == "" else str(v).strip())
    for col in ("date", "due_date", "paid_date"):
        df[col] = pd.to_datetime(df[col], errors="coerce")
    for col in ("amount", "balance_after"):
        df[col] = pd.to_numeric(df[col], errors="coerce").astype(float)
    df["_order"] = range(len(df))
    return df


@dataclass
class Window:
    as_of: pd.Timestamp
    start: pd.Timestamp
    months: list[pd.Period]


def make_window(df: pd.DataFrame, as_of: pd.Timestamp | None = None) -> Window:
    if as_of is None:
        dates = pd.concat([df["date"], df["paid_date"]]).dropna()
        as_of = dates.max() if len(dates) else pd.Timestamp.today().normalize()
    as_of = pd.Timestamp(as_of).normalize()
    end = as_of.to_period("M")
    months = list(pd.period_range(end - (C.WINDOW_MONTHS - 1), end, freq="M"))
    return Window(as_of=as_of, start=months[0].start_time, months=months)


def _scale(key: str, metric: float) -> float:
    ind = C.INDICATOR_BY_KEY[key]
    xs = [p[0] for p in ind.thresholds]
    ys = [p[1] for p in ind.thresholds]
    return float(round_half_up(float(np.interp(metric, xs, ys))))


def _insufficient(reason: str, **details: Any) -> dict:
    return {"status": "insufficient_data", "metric": None, "sub_score": None, "reason": reason, "details": details}


def _scored(key: str, metric: float, **details: Any) -> dict:
    return {"status": "scored", "metric": float(metric), "sub_score": _scale(key, metric), "reason": None, "details": details}


# ---------------------------------------------------------------------------
# Monthly series
# ---------------------------------------------------------------------------

def monthly_series(df: pd.DataFrame, w: Window) -> pd.DataFrame:
    """Per-month inflow (business income), outflow, net and month-end balance.

    Months with no bank records at all are NaN, never zero.
    """
    bank = df[(df.record_type == "bank") & (df.date >= w.start) & (df.date <= w.as_of)].copy()
    bank["month"] = bank["date"].dt.to_period("M")
    is_income = (bank.direction == "credit") & ~bank.category.isin(C.NON_INCOME_CREDIT_CATEGORIES)
    out = pd.DataFrame(index=pd.PeriodIndex(w.months, freq="M"))
    present = set(bank["month"].unique())
    inflow = bank[is_income].groupby("month")["amount"].sum()
    outflow = bank[bank.direction == "debit"].groupby("month")["amount"].sum()
    other_credit = bank[(bank.direction == "credit") & ~is_income].groupby("month")["amount"].sum()
    out["has_bank"] = [m in present for m in out.index]
    out["inflow"] = [float(inflow.get(m, 0.0)) if m in present else np.nan for m in out.index]
    out["outflow"] = [float(outflow.get(m, 0.0)) if m in present else np.nan for m in out.index]
    out["other_credit"] = [float(other_credit.get(m, 0.0)) if m in present else np.nan for m in out.index]
    out["net"] = out["inflow"] - out["outflow"]
    bal = bank.dropna(subset=["balance_after"]).sort_values(["date", "_order"])
    month_end = bal.groupby("month")["balance_after"].last()
    out["month_end_balance"] = [float(month_end[m]) if m in month_end.index else np.nan for m in out.index]
    sales = df[(df.record_type == "sale") & (df.date >= w.start) & (df.date <= w.as_of)].copy()
    sales["month"] = sales["date"].dt.to_period("M")
    sales_m = sales.groupby("month")["amount"].sum()
    out["sales_register"] = [float(sales_m[m]) if m in sales_m.index else np.nan for m in out.index]
    return out


# ---------------------------------------------------------------------------
# Indicator metrics
# ---------------------------------------------------------------------------

def m_cash_flow_stability(ms: pd.DataFrame) -> dict:
    s = ms[ms.has_bank]
    if len(s) < C.MIN_MONTHS_FOR_VOLATILITY:
        return _insufficient(f"Needs at least {C.MIN_MONTHS_FOR_VOLATILITY} months of bank records; found {len(s)}.", months=len(s))
    mean_in = s.inflow.mean()
    std_net = float(np.std(s.net.values, ddof=0))
    if mean_in <= 0:
        return {**_scored("cash_flow_stability", 1.0), "details": {"months": len(s), "note": "No business income observed"}}
    neg_months = int((s.net < 0).sum())
    return _scored(
        "cash_flow_stability",
        std_net / mean_in,
        months=len(s),
        std_net=round(std_net),
        mean_net=round(float(s.net.mean())),
        mean_inflow=round(float(mean_in)),
        negative_months=neg_months,
    )


def m_revenue_consistency(ms: pd.DataFrame) -> dict:
    s = ms[ms.has_bank]
    if len(s) < C.MIN_MONTHS_FOR_VOLATILITY:
        return _insufficient(f"Needs at least {C.MIN_MONTHS_FOR_VOLATILITY} months of bank records; found {len(s)}.", months=len(s))
    mean_in = s.inflow.mean()
    if mean_in <= 0:
        return {**_scored("revenue_consistency", 1.0), "details": {"months": len(s), "note": "No business income observed"}}
    cv = float(np.std(s.inflow.values, ddof=0)) / mean_in
    return _scored(
        "revenue_consistency",
        cv,
        months=len(s),
        mean_inflow=round(float(mean_in)),
        min_inflow=round(float(s.inflow.min())),
        max_inflow=round(float(s.inflow.max())),
    )


def m_repayment_record(df: pd.DataFrame, w: Window) -> dict:
    cfg = C.INDICATOR_BY_KEY["repayment_record"].extra
    grace = pd.Timedelta(days=cfg["grace_days"])
    loans = df[(df.record_type == "loan_repayment") & (df.date >= w.start) & (df.date <= w.as_of)].copy()
    paid = loans.paid_date.notna() & (loans.paid_date <= w.as_of)
    # An unpaid instalment still inside its grace period is not late yet.
    still_open = ~paid & (loans.date + grace > w.as_of)
    loans = loans[~still_open]
    paid = loans.paid_date.notna() & (loans.paid_date <= w.as_of)
    if len(loans) < cfg["min_instalments"]:
        reason = (
            "No loan repayment history shared - thin credit file."
            if len(loans) == 0
            else f"Only {len(loans)} instalment(s) due in the window; at least {cfg['min_instalments']} needed."
        )
        return _insufficient(reason, instalments=len(loans))
    on_time = paid & (loans.paid_date <= loans.date + grace)
    late = paid & ~on_time
    missed = ~paid
    late_rows = loans[late | missed]
    return _scored(
        "repayment_record",
        float(on_time.mean()),
        instalments=len(loans),
        on_time=int(on_time.sum()),
        late=int(late.sum()),
        missed=int(missed.sum()),
        late_items=[
            {
                "reference": r.reference,
                "due_date": r.date.date().isoformat(),
                "paid_date": r.paid_date.date().isoformat() if pd.notna(r.paid_date) and r.paid_date <= w.as_of else None,
                "days_late": int((r.paid_date - r.date).days) if pd.notna(r.paid_date) and r.paid_date <= w.as_of else None,
                "amount": r.amount,
            }
            for r in late_rows.itertuples()
        ],
    )


def m_debt_burden(df: pd.DataFrame, ms: pd.DataFrame, w: Window) -> dict:
    s = ms[ms.has_bank]
    if len(s) == 0 or s.inflow.mean() <= 0:
        return _insufficient("Needs bank records with business income to compare debt service against.")
    mean_in = float(s.inflow.mean())
    loans = df[(df.record_type == "loan_repayment") & (df.date >= w.start) & (df.date <= w.as_of)].copy()
    source = "loan_records"
    if len(loans):
        loans["month"] = loans.date.dt.to_period("M")
        monthly = loans.groupby("month")["amount"].sum()
    else:
        emi = df[(df.record_type == "bank") & (df.category == "loan_emi") & (df.direction == "debit") & (df.date >= w.start) & (df.date <= w.as_of)].copy()
        emi["month"] = emi.date.dt.to_period("M")
        monthly = emi.groupby("month")["amount"].sum()
        source = "bank_emi_debits" if len(emi) else "none_observed"
    service = float(monthly.mean()) if len(monthly) else 0.0
    return _scored(
        "debt_burden",
        service / mean_in,
        monthly_debt_service=round(service),
        mean_inflow=round(mean_in),
        source=source,
    )


def m_invoice_collection(df: pd.DataFrame, w: Window) -> dict:
    inv = df[(df.record_type == "invoice") & (df.date >= w.start) & (df.date <= w.as_of)].copy()
    due = inv[inv.due_date <= w.as_of]
    not_due = inv[inv.due_date > w.as_of]
    if len(due) == 0:
        return _insufficient(
            "No invoices due in the window (normal for cash/UPI-only businesses).",
            invoices=len(inv),
        )
    paid = due.paid_date.notna() & (due.paid_date <= w.as_of)
    on_time = paid & (due.paid_date <= due.due_date)
    total = float(due.amount.sum())
    on_time_share = float(due.amount[on_time].sum()) / total
    overdue_mask = ~paid
    overdue_share = float(due.amount[overdue_mask].sum()) / total
    overdue = due[overdue_mask].sort_values("due_date")
    return _scored(
        "invoice_collection",
        0.5 * on_time_share + 0.5 * (1 - overdue_share),
        invoices_due=len(due),
        invoices_not_yet_due=len(not_due),
        value_due=round(total),
        on_time_share=round(on_time_share, 4),
        late_paid_share=round(float(due.amount[paid & ~on_time].sum()) / total, 4),
        overdue_share=round(overdue_share, 4),
        overdue_value=round(float(due.amount[overdue_mask].sum())),
        overdue_items=[
            {
                "reference": r.reference,
                "counterparty": r.counterparty,
                "issued": r.date.date().isoformat(),
                "due_date": r.due_date.date().isoformat(),
                "days_overdue": int((w.as_of - r.due_date).days),
                "amount": r.amount,
            }
            for r in overdue.itertuples()
        ],
    )


def m_liquidity(ms: pd.DataFrame) -> dict:
    s = ms[ms.has_bank]
    bal = s.month_end_balance.dropna()
    if len(bal) < C.MIN_MONTHS_FOR_VOLATILITY:
        return _insufficient(
            f"Needs account balances (balance_after) for at least {C.MIN_MONTHS_FOR_VOLATILITY} months; found {len(bal)}.",
            months_with_balance=len(bal),
        )
    mean_out = float(s.outflow.mean())
    mean_bal = float(bal.mean())
    days = 999.0 if mean_out <= 0 else mean_bal / (mean_out / 30.0)
    return _scored(
        "liquidity_resilience",
        days,
        mean_month_end_balance=round(mean_bal),
        mean_monthly_outflow=round(mean_out),
        lowest_month_end_balance=round(float(bal.min())),
        months_with_balance=len(bal),
    )


def completeness_breakdown(df: pd.DataFrame, w: Window) -> dict:
    win = df[(df.date >= w.start) & (df.date <= w.as_of)].copy()
    win["month"] = win.date.dt.to_period("M")
    coverage: dict[str, dict] = {}
    for rt in C.CORE_RECORD_TYPES + C.OPTIONAL_RECORD_TYPES:
        rows = win[win.record_type == rt]
        present = sorted(set(rows.month))
        if rt in C.OPTIONAL_RECORD_TYPES and not present:
            continue  # not expected unless the business has this kind of record
        if rt == "loan_repayment":
            expected = [m for m in w.months if m >= present[0]]
        else:
            expected = list(w.months)
        missing = [m for m in expected if m not in present]
        coverage[rt] = {
            "expected_months": len(expected),
            "months_present": len(expected) - len(missing),
            "share": (len(expected) - len(missing)) / len(expected),
            "missing_months": [str(m) for m in missing],
        }
    total_rows = 0
    complete_rows = 0
    missing_fields: dict[str, int] = {}
    for rt, fields in RECOMMENDED_BY_TYPE.items():
        rows = win[win.record_type == rt]
        if not len(rows):
            continue
        ok = pd.Series(True, index=rows.index)
        for f in fields:
            miss = rows[f].isna()
            if miss.any():
                missing_fields[f"{rt}.{f}"] = int(miss.sum())
            ok &= ~miss
        total_rows += len(rows)
        complete_rows += int(ok.sum())
    field_share = complete_rows / total_rows if total_rows else 0.0
    cov_share = float(np.mean([c["share"] for c in coverage.values()])) if coverage else 0.0
    return {
        "coverage": coverage,
        "coverage_share": round(cov_share, 4),
        "rows": total_rows,
        "complete_rows": complete_rows,
        "field_share": round(field_share, 4),
        "missing_fields": missing_fields,
        "_metric": cov_share * field_share,
    }


def m_data_completeness(df: pd.DataFrame, w: Window) -> dict:
    b = completeness_breakdown(df, w)
    metric = b.pop("_metric")
    return _scored("data_completeness", metric, **b)


def m_growth(df: pd.DataFrame, w: Window) -> dict:
    cfg = C.INDICATOR_BY_KEY["growth_seasonality"].extra
    bank = df[(df.record_type == "bank") & (df.date <= w.as_of)].copy()
    bank["month"] = bank.date.dt.to_period("M")
    is_income = (bank.direction == "credit") & ~bank.category.isin(C.NON_INCOME_CREDIT_CATEGORIES)
    present = set(bank.month)
    income = bank[is_income].groupby("month")["amount"].sum()
    series = {m: float(income.get(m, 0.0)) for m in present}
    window_months = [m for m in w.months if m in series]
    prior = [m - 12 for m in window_months if (m - 12) in series]
    if len(prior) >= 6:
        cur = sum(series[m + 12] for m in prior)
        prev = sum(series[m] for m in prior)
        if prev > 0:
            return _scored("growth_seasonality", cur / prev - 1, method="same_month_yoy", months_compared=len(prior))
    if len(window_months) < cfg["min_months"]:
        return _insufficient(f"Needs at least {cfg['min_months']} months of income to estimate growth; found {len(window_months)}.")
    x = np.array([(m - w.months[0]).n for m in window_months], dtype=float)
    y = np.array([series[m] for m in window_months])
    if y.mean() <= 0:
        return _insufficient("No business income observed.")
    slope = float(np.polyfit(x, y, 1)[0])
    return _scored(
        "growth_seasonality",
        slope * 12 / float(y.mean()),
        method="linear_trend",
        months=len(window_months),
        note="Fewer than 24 months of data: growth is a trend estimate and cannot yet compare the same months year-on-year.",
    )


# ---------------------------------------------------------------------------
# Weighted score — the single scoring function
# ---------------------------------------------------------------------------

def compute_overall(sub_scores: dict[str, float | None]) -> dict:
    """Overall = sum(sub-score x weight), re-normalising weights over scored indicators."""
    scored = {k: v for k, v in sub_scores.items() if v is not None}
    total_w = sum(C.INDICATOR_BY_KEY[k].weight for k in scored)
    rows = []
    for ind in C.INDICATORS:
        s = sub_scores.get(ind.key)
        eff = ind.weight / total_w if s is not None and total_w > 0 else 0.0
        rows.append(
            {
                "key": ind.key,
                "weight": ind.weight,
                "effective_weight": round(eff, 6),
                "sub_score": s,
                "contribution": round(s * eff, 4) if s is not None else None,
            }
        )
    overall = sum(r["contribution"] for r in rows if r["contribution"] is not None) if scored else None
    return {
        "overall": round(overall, 2) if overall is not None else None,
        "display": int(round_half_up(overall)) if overall is not None else None,
        "scored_weight": round(total_w, 6),
        "indicators": rows,
    }


def band(sub_score: float | None) -> str:
    if sub_score is None:
        return "insufficient_data"
    if sub_score >= C.STRENGTH_MIN:
        return "strength"
    if sub_score < C.CONCERN_BELOW:
        return "concern"
    return "watch"


def not_applicable(ind_key: str, result: dict) -> bool:
    """An unscored indicator that simply does not apply to this business.

    A cash/UPI-only shop has no invoices; that is not a data gap.
    """
    return ind_key == "invoice_collection" and result["status"] == "insufficient_data" and result["details"].get("invoices", 0) == 0


def confidence(bank_months: int, completeness: float | None, results: dict[str, dict]) -> dict:
    """Confidence level plus the checks behind it, so the reasoning can be shown."""
    R = C.CONFIDENCE_RULES

    def grade(value: float, rule: dict, higher_is_better: bool = True) -> str:
        if higher_is_better:
            return "pass" if value >= rule["pass"] else "warn" if value >= rule["warn"] else "fail"
        return "pass" if value <= rule["pass"] else "warn" if value <= rule["warn"] else "fail"

    na = [k for k, r in results.items() if not_applicable(k, r)]
    missing = [C.INDICATOR_BY_KEY[k].name for k, r in results.items() if r["sub_score"] is None and k not in na]
    applicable = len(results) - len(na)
    comp = completeness if completeness is not None else 0.0
    checks = [
        {
            "key": "bank_months",
            "label": "Bank / UPI history",
            "value": f"{bank_months} of {C.WINDOW_MONTHS} months",
            "status": grade(bank_months, R["bank_months"]),
            "rule": f"{R['bank_months']['pass']}+ months passes; {R['bank_months']['warn']}-{R['bank_months']['pass'] - 1} is a warning; fewer fails",
        },
        {
            "key": "completeness",
            "label": "Record completeness",
            "value": f"{comp:.0f} / 100",
            "status": grade(comp, R["completeness"]),
            "rule": f"{R['completeness']['pass']}+ passes; {R['completeness']['warn']}-{R['completeness']['pass'] - 1} is a warning; lower fails",
        },
        {
            "key": "missing_indicators",
            "label": "Indicators scored",
            "value": f"{applicable - len(missing)} of {applicable} applicable"
            + (f" (not applicable: {', '.join(C.INDICATOR_BY_KEY[k].name.lower() for k in na)})" if na else ""),
            "status": grade(len(missing), R["missing_indicators"], higher_is_better=False),
            "rule": f"All applicable passes; up to {R['missing_indicators']['warn']} unscored is a warning; more fails",
            "detail": ("Not enough data: " + ", ".join(missing)) if missing else None,
        },
    ]
    statuses = {c["status"] for c in checks}
    level = "low" if "fail" in statuses else "medium" if "warn" in statuses else "high"
    reasons = [f"{c['label']}: {c['value']}" for c in checks if c["status"] != "pass"] or [
        f"{bank_months} months of bank data, complete records and all applicable indicators scored"
    ]
    return {"level": level, "reasons": reasons, "checks": checks}


def score_records(df: pd.DataFrame, as_of: pd.Timestamp | None = None) -> dict:
    """Run every indicator and the weighted score. Pure function of the records."""
    w = make_window(df, as_of)
    df = df[df.date <= w.as_of]
    ms = monthly_series(df, w)
    results = {
        "cash_flow_stability": m_cash_flow_stability(ms),
        "revenue_consistency": m_revenue_consistency(ms),
        "repayment_record": m_repayment_record(df, w),
        "debt_burden": m_debt_burden(df, ms, w),
        "invoice_collection": m_invoice_collection(df, w),
        "liquidity_resilience": m_liquidity(ms),
        "data_completeness": m_data_completeness(df, w),
        "growth_seasonality": m_growth(df, w),
    }
    overall = compute_overall({k: v["sub_score"] for k, v in results.items()})
    by_key = {r["key"]: r for r in overall["indicators"]}
    indicators = []
    for ind in C.INDICATORS:
        r = results[ind.key]
        indicators.append(
            {
                "key": ind.key,
                "name": ind.name,
                "weight": ind.weight,
                "effective_weight": by_key[ind.key]["effective_weight"],
                "sub_score": r["sub_score"],
                "contribution": by_key[ind.key]["contribution"],
                "status": r["status"],
                "band": band(r["sub_score"]),
                "metric": r["metric"],
                "metric_label": ind.metric_label,
                "benchmark": ind.benchmark,
                "reason": r["reason"],
                "details": r["details"],
            }
        )
    bank_months = int(ms.has_bank.sum())
    return {
        "as_of": w.as_of.date().isoformat(),
        "window_start": w.start.date().isoformat(),
        "window_end": w.as_of.date().isoformat(),
        "window_months": [str(m) for m in w.months],
        "overall_score": overall["overall"],
        "display_score": overall["display"],
        "scored_weight": overall["scored_weight"],
        "indicators": indicators,
        "monthly": ms,
        "window": w,
        "confidence": confidence(bank_months, results["data_completeness"]["sub_score"], results),
        "bank_months": bank_months,
    }
