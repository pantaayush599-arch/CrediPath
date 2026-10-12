"""Data-quality, consistency and anomaly checks.

Every flag here is a prompt for a human to look closer. None of them is
evidence of fraud, and none of them changes the score directly: missing data
lowers data completeness through the indicator itself, and the other flags
are shown alongside the score for the loan officer to verify.
"""

from __future__ import annotations

import pandas as pd

from . import config as C
from .engine import Window
from .explain import group_in

A = C.ANOMALY

LABELS = {
    "bank": "bank / UPI statements",
    "sale": "sales register",
    "invoice": "invoices",
    "supplier_payment": "supplier payments",
    "loan_repayment": "loan repayments",
}


def _flag(kind, severity, title, detail, verify=False, evidence=None, category="risk"):
    return {
        "kind": kind,
        "severity": severity,  # info | warning | high
        "category": category,  # data_quality | risk | verification
        "title": title,
        "detail": detail,
        "requires_verification": verify,
        "evidence": evidence or {},
    }


def _inr(x: float) -> str:
    return ("-" if x < 0 else "") + "₹" + group_in(round(x))


def missing_data_flags(indicators: list[dict]) -> list[dict]:
    flags = []
    comp = next(i for i in indicators if i["key"] == "data_completeness")["details"]
    for rt, c in comp.get("coverage", {}).items():
        if c["missing_months"]:
            n = len(c["missing_months"])
            flags.append(
                _flag(
                    "missing_data",
                    "warning" if n >= 3 else "info",
                    f"{LABELS[rt][0].upper() + LABELS[rt][1:]} missing for {n} of {c['expected_months']} months",
                    f"No {LABELS[rt]} were shared for: {', '.join(c['missing_months'])}. Missing months are not counted as zero; they lower data completeness.",
                    category="data_quality",
                    evidence={"record_type": rt, "missing_months": c["missing_months"]},
                )
            )
    if comp.get("missing_fields"):
        total = sum(comp["missing_fields"].values())
        parts = ", ".join(f"{k} ({v})" for k, v in comp["missing_fields"].items())
        flags.append(
            _flag(
                "missing_fields",
                "info",
                f"{total} blank values in recommended fields",
                f"Blank fields by type: {parts}. Blanks are left empty, not filled with zero.",
                category="data_quality",
                evidence={"missing_fields": comp["missing_fields"]},
            )
        )
    for ind in indicators:
        if ind["status"] == "insufficient_data":
            flags.append(
                _flag(
                    "insufficient_data",
                    "info",
                    f"{ind['name']}: not enough data to score",
                    f"{ind['reason']} This indicator is left out and the other weights are re-normalised.",
                    category="data_quality",
                    evidence={"indicator": ind["key"]},
                )
            )
    return flags


def circular_flow_flags(df: pd.DataFrame, w: Window) -> list[dict]:
    bank = df[(df.record_type == "bank") & (df.date >= w.start) & (df.date <= w.as_of) & df.counterparty.notna()]
    bank = bank[bank.amount >= A["circular_min_amount"]]
    debits = bank[bank.direction == "debit"]
    credits = bank[bank.direction == "credit"]
    flags = []
    used: set = set()
    for d in debits.itertuples():
        cands = credits[
            (credits.counterparty.str.lower() == d.counterparty.lower())
            & ((credits.date - d.date).abs() <= pd.Timedelta(days=A["circular_window_days"]))
            & ((credits.amount - d.amount).abs() <= A["circular_amount_tolerance"] * d.amount)
        ]
        for c in cands.itertuples():
            if c.id in used:
                continue
            used.add(c.id)
            first, second = (d, c) if d.date <= c.date else (c, d)
            flags.append(
                _flag(
                    "circular_flow",
                    "high",
                    f"Possible circular flow with {d.counterparty}",
                    f"{_inr(first.amount)} {'sent to' if first is d else 'received from'} {d.counterparty} on {first.date.date()} "
                    f"and {_inr(second.amount)} {'received back' if second is c else 'sent back'} on {second.date.date()}. "
                    "Round-tripped money can inflate apparent turnover. Verify the purpose of both transactions.",
                    verify=True,
                    evidence={"debit_id": int(d.id), "credit_id": int(c.id), "counterparty": d.counterparty, "amounts": [d.amount, c.amount]},
                )
            )
            break
    return flags


def spike_flags(df: pd.DataFrame, w: Window) -> list[dict]:
    bank = df[(df.record_type == "bank") & (df.direction == "credit") & (df.date >= w.start) & (df.date <= w.as_of)].copy()
    if len(bank) < 6:
        return []
    bank = bank[~bank.category.isin(C.NON_INCOME_CREDIT_CATEGORIES)]
    bank["month"] = bank.date.dt.to_period("M")
    month_tot = bank.groupby("month")["amount"].sum()
    median = float(bank.amount.median())
    flags = []
    for r in bank.itertuples():
        share = r.amount / month_tot[r.month]
        if share >= A["spike_share_of_month"] and r.amount >= A["spike_multiple_of_median"] * median:
            flags.append(
                _flag(
                    "one_off_spike",
                    "warning",
                    f"Unusual one-off credit of {_inr(r.amount)}",
                    f"Received {r.date.date()} from {r.counterparty or 'an unnamed payer'}: {share:.0%} of that month's income and "
                    f"{r.amount / median:.1f}x the typical credit. It is included in income; verify whether it is recurring business revenue.",
                    verify=True,
                    evidence={"record_id": int(r.id), "amount": r.amount, "share_of_month": round(share, 3)},
                )
            )
    return flags


def mismatch_flags(df: pd.DataFrame, w: Window, monthly: pd.DataFrame) -> list[dict]:
    flags = []
    win = df[(df.date >= w.start) & (df.date <= w.as_of)]
    bank = df[(df.record_type == "bank") & (df.date <= w.as_of)]
    tol_days = pd.Timedelta(days=A["match_window_days"])

    def has_match(direction, amount, when, party):
        c = bank[
            (bank.direction == direction)
            & ((bank.date - when).abs() <= tol_days)
            & ((bank.amount - amount).abs() <= A["match_amount_tolerance"] * amount)
        ]
        if party is None:
            return len(c) > 0
        # A blank bank counterparty can still be the match; a different name cannot.
        return bool((c.counterparty.isna() | (c.counterparty.str.lower() == party.lower())).any())

    bank_months = set(monthly.index[monthly.has_bank])
    unmatched_inv = []
    for r in win[(win.record_type == "invoice") & win.paid_date.notna() & (win.paid_date <= w.as_of)].itertuples():
        if r.paid_date.to_period("M") in bank_months and not has_match("credit", r.amount, r.paid_date, r.counterparty):
            unmatched_inv.append({"reference": r.reference, "counterparty": r.counterparty, "amount": r.amount, "paid_date": r.paid_date.date().isoformat()})
    if unmatched_inv:
        flags.append(
            _flag(
                "record_mismatch",
                "warning",
                f"{len(unmatched_inv)} paid invoice(s) with no matching bank credit",
                "These invoices are marked paid but no credit of the same amount appears in the bank records within "
                f"{A['match_window_days']} days of the paid date.",
                verify=True,
                evidence={"items": unmatched_inv},
            )
        )
    unmatched_sup = []
    for r in win[win.record_type == "supplier_payment"].itertuples():
        when = r.paid_date if pd.notna(r.paid_date) else r.date
        if when.to_period("M") in bank_months and not has_match("debit", r.amount, when, r.counterparty):
            unmatched_sup.append({"counterparty": r.counterparty, "amount": r.amount, "date": when.date().isoformat()})
    if unmatched_sup:
        flags.append(
            _flag(
                "record_mismatch",
                "warning",
                f"{len(unmatched_sup)} supplier payment(s) not found in bank records",
                f"Supplier ledger entries with no bank debit of the same amount within {A['match_window_days']} days.",
                verify=True,
                evidence={"items": unmatched_sup},
            )
        )
    gaps = []
    for m, row in monthly.iterrows():
        if pd.notna(row.sales_register) and pd.notna(row.inflow) and row.inflow > 0:
            diff = (row.sales_register - row.inflow) / row.inflow
            if abs(diff) > A["sales_vs_bank_tolerance"]:
                gaps.append({"month": str(m), "sales_register": row.sales_register, "bank_income": row.inflow, "difference": round(diff, 3)})
    if gaps:
        flags.append(
            _flag(
                "record_mismatch",
                "warning",
                f"Sales register differs from bank income in {len(gaps)} month(s)",
                f"Recorded sales differ from bank income by more than {A['sales_vs_bank_tolerance']:.0%} (cash sales not deposited can explain this).",
                verify=True,
                evidence={"items": gaps},
            )
        )
    return flags


def verification_flags(indicators: list[dict]) -> list[dict]:
    flags = []
    inv = next(i for i in indicators if i["key"] == "invoice_collection")
    if inv["status"] == "scored" and inv["details"].get("overdue_items"):
        d = inv["details"]
        items = d["overdue_items"]
        flags.append(
            _flag(
                "overdue_receivables",
                "warning",
                f"Verify: {len(items)} overdue receivable(s) worth {_inr(d['overdue_value'])}",
                f"{d['overdue_share']:.0%} of invoice value due in the window is unpaid past its due date. "
                "Confirm with the customers whether these are collectable.",
                verify=True,
                category="verification",
                evidence={"items": items},
            )
        )
    rep = next(i for i in indicators if i["key"] == "repayment_record")
    if rep["status"] == "scored" and rep["details"].get("late_items"):
        items = rep["details"]["late_items"]
        missed = sum(1 for x in items if x["paid_date"] is None)
        flags.append(
            _flag(
                "late_repayment",
                "warning" if missed else "info",
                f"{len(items)} loan instalment(s) paid late or missed",
                f"{len(items) - missed} paid after the 5-day grace period, {missed} not paid.",
                verify=bool(missed),
                evidence={"items": items},
            )
        )
    debt = next(i for i in indicators if i["key"] == "debt_burden")
    if debt["status"] == "scored" and debt["details"].get("source") == "none_observed":
        flags.append(
            _flag(
                "no_debt_observed",
                "info",
                "No loan repayments observed",
                "No EMIs appear in the shared records, so debt burden is scored as none observed. Confirm against the credit bureau.",
                verify=True,
                category="verification",
            )
        )
    return flags


def run_checks(df: pd.DataFrame, w: Window, monthly: pd.DataFrame, indicators: list[dict], confidence: dict) -> list[dict]:
    df = df[df.date <= w.as_of]
    flags = (
        verification_flags(indicators)
        + circular_flow_flags(df, w)
        + spike_flags(df, w)
        + mismatch_flags(df, w, monthly)
        + missing_data_flags(indicators)
    )
    if confidence["level"] == "low":
        flags.append(
            _flag(
                "low_confidence",
                "high",
                "Low-confidence assessment",
                "Thin data: " + "; ".join(confidence["reasons"]) + ". Treat the score as provisional.",
                category="data_quality",
            )
        )
    order = {"high": 0, "warning": 1, "info": 2}
    return sorted(flags, key=lambda f: order[f["severity"]])
