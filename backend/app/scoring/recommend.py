"""Ranked improvement plan and the what-if simulator.

A recommendation exists for every scored indicator below its benchmark. Its
estimated impact is what the *same* weighted formula gives if that indicator
reached its benchmark and nothing else changed. These are hypothetical
estimates, never applied to the real assessment.
"""

from __future__ import annotations

from . import config as C
from .engine import compute_overall, round_half_up
from .explain import inr, pct

TEMPLATES = {
    "invoice_collection": {
        "action_key": "collect_overdue_invoices",
        "title": "Collect overdue invoices",
        "short": "Invoices",
        "steps": [
            "Call or message each customer with an overdue invoice and agree a payment date.",
            "Send a UPI payment link with every invoice so customers can pay in one tap.",
            "Shorten credit to 15 days for customers who pay late repeatedly.",
        ],
    },
    "data_completeness": {
        "action_key": "complete_records",
        "title": "Complete your financial records",
        "short": "Records",
        "steps": [
            "Upload the missing months of your sales register and supplier payments.",
            "Include the account balance and payer/payee name for each bank entry.",
            "Keep invoice numbers on every invoice so payments can be matched.",
        ],
    },
    "cash_flow_stability": {
        "action_key": "stabilise_cash_flow",
        "title": "Stabilise cash flow",
        "short": "Cash",
        "steps": [
            "Spread large stock purchases over the month instead of one bulk payment.",
            "Ask key suppliers for 15-30 day payment terms around festival stocking.",
            "Set aside a fixed amount each week for rent, salaries and EMIs.",
        ],
    },
    "liquidity_resilience": {
        "action_key": "build_cash_buffer",
        "title": "Build a cash buffer",
        "short": "Liquidity",
        "steps": [
            "Keep at least 4 weeks of regular expenses in the business account.",
            "Move surplus from good months into the account rather than withdrawing it.",
        ],
    },
    "debt_burden": {
        "action_key": "reduce_debt_burden",
        "title": "Reduce your loan burden",
        "short": "Debt",
        "steps": [
            "Avoid taking new loans until existing EMIs are below 10% of income.",
            "Pre-pay the costliest loan first when you have surplus cash.",
        ],
    },
    "repayment_record": {
        "action_key": "pay_emis_on_time",
        "title": "Pay every EMI on time",
        "short": "EMIs",
        "steps": [
            "Set up auto-debit (NACH) for each loan instalment.",
            "Keep the EMI amount in the account two days before the due date.",
        ],
    },
    "revenue_consistency": {
        "action_key": "steady_sales",
        "title": "Make sales more regular",
        "short": "Sales",
        "steps": [
            "Route more sales through UPI or card so all income shows in the bank.",
            "Add repeat or subscription customers to smooth slow months.",
        ],
    },
    "growth_seasonality": {
        "action_key": "grow_income",
        "title": "Grow income in slow seasons",
        "short": "Growth",
        "steps": [
            "Plan offers for months that are usually slow.",
            "Add a product line that sells in your off-season.",
        ],
    },
}

ACTION_TO_INDICATOR = {t["action_key"]: k for k, t in TEMPLATES.items()}


def _why(ind: dict) -> str:
    d = ind["details"]
    k = ind["key"]
    if k == "invoice_collection" and d.get("overdue_value"):
        return f"{len(d.get('overdue_items', []))} invoices worth {inr(d['overdue_value'])} are overdue."
    if k == "data_completeness":
        gaps = [f"{rt.replace('_', ' ')} for {c['expected_months'] - c['months_present']} months" for rt, c in d.get("coverage", {}).items() if c["share"] < 1]
        return ("Missing " + ", ".join(gaps) + ".") if gaps else f"{pct(1 - d.get('field_share', 1))} of rows have blank details."
    if k == "cash_flow_stability":
        return f"Money left over each month swings by about {inr(d.get('std_net'))}."
    if k == "liquidity_resilience":
        return f"Your balance covers about {ind['metric']:.0f} days of spending; 26+ days is the benchmark."
    if k == "debt_burden":
        return f"EMIs take {pct(ind['metric'])} of income."
    if k == "repayment_record":
        return f"{d.get('late', 0) + d.get('missed', 0)} instalments were late or missed."
    return ind["metric_label"]


def build_plan(indicators: list[dict]) -> list[dict]:
    """All candidate actions, ranked by estimated score impact (ties: fixed priority)."""
    base = compute_overall({i["key"]: i["sub_score"] for i in indicators})["overall"]
    cands = []
    for ind in indicators:
        if ind["sub_score"] is None or ind["sub_score"] >= ind["benchmark"]:
            continue
        t = TEMPLATES[ind["key"]]
        subs = {i["key"]: i["sub_score"] for i in indicators}
        subs[ind["key"]] = float(ind["benchmark"])
        impact = round(compute_overall(subs)["overall"] - base, 2)
        cands.append(
            {
                "action_key": t["action_key"],
                "indicator_key": ind["key"],
                "indicator_name": ind["name"],
                "title": t["title"],
                "short_label": t["short"],
                "why": _why(ind),
                "steps": t["steps"],
                "current_sub_score": ind["sub_score"],
                "target_sub_score": float(ind["benchmark"]),
                "expected_impact": impact,
            }
        )
    cands.sort(key=lambda c: (-c["expected_impact"], C.ACTION_PRIORITY.index(c["indicator_key"])))
    for n, c in enumerate(cands, 1):
        c["rank"] = n
        c["in_top_plan"] = n <= C.PLAN_SIZE
    return cands


def what_if(indicators: list[dict], plan: list[dict], selected_actions: list[str]) -> dict:
    """Hypothetical score if the selected actions brought their indicators to benchmark."""
    subs = {i["key"]: i["sub_score"] for i in indicators}
    base = compute_overall(subs)
    by_action = {p["action_key"]: p for p in plan}
    unknown = [a for a in selected_actions if a not in by_action]
    steps = []
    running = dict(subs)
    prev = base["overall"]
    for p in plan:  # apply in plan order so the step chart is stable
        if p["action_key"] not in selected_actions:
            continue
        running[p["indicator_key"]] = p["target_sub_score"]
        now = compute_overall(running)["overall"]
        steps.append({**{k: p[k] for k in ("action_key", "short_label", "title", "indicator_key", "current_sub_score", "target_sub_score")}, "delta": round(now - prev, 2)})
        prev = now
    after = compute_overall(running)
    return {
        "hypothetical": True,
        "baseline_score": base["overall"],
        "baseline_display": base["display"],
        "hypothetical_score": after["overall"],
        "hypothetical_display": int(round_half_up(after["overall"])) if after["overall"] is not None else None,
        "total_delta": round(after["overall"] - base["overall"], 2) if after["overall"] is not None else 0,
        "steps": steps,
        "ignored_actions": unknown,
        "note": "Hypothetical estimate: each selected action is assumed to lift its indicator to the benchmark, scored with the same weighted formula. It does not change your real assessment, which only changes when new records are uploaded and rescored. It is not a promise of loan eligibility.",
    }
