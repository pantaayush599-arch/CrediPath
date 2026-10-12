"""Template-based explanations.

Turns the structured scoring output into sentences for the banker (precise,
metric-level) and the merchant (plain language). Every number in a sentence
comes from the scoring output; nothing here changes a score.
"""

from __future__ import annotations

from . import config as C


def group_in(n: int) -> str:
    """Indian digit grouping: 1234567 -> 12,34,567."""
    s = str(abs(n))
    if len(s) <= 3:
        return s
    head, tail = s[:-3], s[-3:]
    parts = []
    while len(head) > 2:
        parts.insert(0, head[-2:])
        head = head[:-2]
    if head:
        parts.insert(0, head)
    return ",".join(parts) + "," + tail


def inr(x: float | None) -> str:
    if x is None:
        return "-"
    x = float(x)
    sign = "-" if x < 0 else ""
    if abs(x) >= 1e5:
        return f"{sign}₹{abs(x) / 1e5:.2f} L".replace(".00 L", " L")
    return f"{sign}₹{group_in(round(x))}"


def pct(x: float | None, digits: int = 0) -> str:
    return "-" if x is None else f"{x * 100:.{digits}f}%"


def indicator_text(ind: dict) -> dict:
    """Return {'banker': str, 'merchant': str} for one indicator."""
    d = ind["details"]
    k = ind["key"]
    if ind["status"] != "scored":
        return {
            "banker": f"Not scored: {ind['reason']}",
            "merchant": f"We could not check this yet. {ind['reason']}",
        }
    m = ind["metric"]
    if k == "cash_flow_stability":
        return {
            "banker": (
                f"Monthly net cash flow (income minus all outflows) has a standard deviation of {inr(d.get('std_net'))} "
                f"= {pct(m, 1)} of average monthly income ({inr(d.get('mean_inflow'))}). "
                f"{d.get('negative_months', 0)} of {d.get('months')} months had negative net flow."
            ),
            "merchant": (
                f"The money left over each month swings by about {inr(d.get('std_net'))} up or down. "
                + ("Some months you spend more than you earn. " if d.get("negative_months") else "")
                + "Smoother months make lenders more comfortable."
            ),
        }
    if k == "revenue_consistency":
        return {
            "banker": (
                f"Monthly business income averaged {inr(d.get('mean_inflow'))} (range {inr(d.get('min_inflow'))} to "
                f"{inr(d.get('max_inflow'))}); coefficient of variation {pct(m, 1)} over {d.get('months')} months."
            ),
            "merchant": f"Your sales come in steadily, about {inr(d.get('mean_inflow'))} a month, without big drops.",
        }
    if k == "repayment_record":
        late = d.get("late", 0) + d.get("missed", 0)
        return {
            "banker": (
                f"{d.get('on_time')} of {d.get('instalments')} instalments paid within the 5-day grace period "
                f"({pct(m)}); {d.get('late')} late, {d.get('missed')} missed."
            ),
            "merchant": (
                f"You paid {d.get('on_time')} of {d.get('instalments')} loan instalments on time."
                + (f" {late} {'was' if late == 1 else 'were'} late." if late else " Keep it up.")
            ),
        }
    if k == "debt_burden":
        src = {"loan_records": "loan records", "bank_emi_debits": "EMI debits in the bank statement", "none_observed": "no EMIs observed"}[d["source"]]
        return {
            "banker": f"Monthly debt service {inr(d.get('monthly_debt_service'))} = {pct(m, 1)} of average monthly income (source: {src}).",
            "merchant": (
                f"Loan instalments take about {pct(m)} of your monthly income."
                if d["source"] != "none_observed"
                else "We did not see any loan instalments in your records."
            ),
        }
    if k == "invoice_collection":
        return {
            "banker": (
                f"{d.get('invoices_due')} invoices worth {inr(d.get('value_due'))} fell due in the window: "
                f"{pct(d.get('on_time_share'))} collected by the due date, {pct(d.get('late_paid_share'))} collected late, "
                f"{pct(d.get('overdue_share'))} ({inr(d.get('overdue_value'))}) still overdue."
            ),
            "merchant": (
                f"Customers who buy on credit owe you {inr(d.get('overdue_value'))} that is past due. "
                f"Only {pct(d.get('on_time_share'))} of invoice value was paid on time."
                if d.get("overdue_value")
                else f"{pct(d.get('on_time_share'))} of your invoice value was paid on time, and nothing is overdue."
            ),
        }
    if k == "liquidity_resilience":
        return {
            "banker": (
                f"Average month-end balance {inr(d.get('mean_month_end_balance'))} against average monthly outflow "
                f"{inr(d.get('mean_monthly_outflow'))} = {m:.1f} days of cover; lowest month-end balance {inr(d.get('lowest_month_end_balance'))}."
            ),
            "merchant": f"Your bank balance could cover about {m:.0f} days of normal spending if sales stopped.",
        }
    if k == "data_completeness":
        cov = d.get("coverage", {})
        gaps = [f"{rt.replace('_', ' ')} {c['months_present']}/{c['expected_months']}" for rt, c in cov.items() if c["share"] < 1]
        return {
            "banker": (
                f"Monthly coverage {pct(d.get('coverage_share'))} (months present: {', '.join(gaps) if gaps else 'complete'}); "
                f"{d.get('complete_rows')} of {d.get('rows')} rows have all recommended fields ({pct(d.get('field_share'))})."
            ),
            "merchant": (
                "Some of your records are missing: " + ", ".join(gaps) + " months shared."
                if gaps
                else "Your records cover every month. Filling in blank details will help further."
            ),
        }
    if k == "growth_seasonality":
        if d.get("method") == "same_month_yoy":
            return {
                "banker": f"Income grew {pct(m, 1)} year-on-year, comparing the same {d.get('months_compared')} months.",
                "merchant": f"Your income is {'up' if m >= 0 else 'down'} {pct(abs(m))} compared with the same months last year.",
            }
        return {
            "banker": f"Linear trend in monthly income implies {pct(m, 1)} annualised growth over {d.get('months')} months (no year-on-year data yet).",
            "merchant": f"Your income has been {'growing' if m >= 0 else 'shrinking'} at roughly {pct(abs(m))} a year.",
        }
    return {"banker": "", "merchant": ""}


MERCHANT_SHORT = {
    "cash_flow_stability": ("steady cash flow", "cash-flow swings"),
    "revenue_consistency": ("steady revenue", "uneven sales"),
    "repayment_record": ("on-time repayments", "late loan repayments"),
    "debt_burden": ("manageable loan instalments", "heavy loan instalments"),
    "invoice_collection": ("customers paying on time", "overdue invoices"),
    "liquidity_resilience": ("a healthy cash buffer", "a thin cash buffer"),
    "data_completeness": ("complete records", "incomplete records"),
    "growth_seasonality": ("growing income", "flat or falling income"),
}


def summaries(result: dict) -> dict:
    inds = result["indicators"]
    strengths = sorted([i for i in inds if i["band"] == "strength"], key=lambda i: -i["sub_score"] * i["weight"])
    concerns = sorted([i for i in inds if i["band"] == "concern"], key=lambda i: -(100 - i["sub_score"]) * i["weight"])
    watch = [i for i in inds if i["band"] == "watch"]
    missing = [i for i in inds if i["band"] == "insufficient_data"]
    score = result["overall_score"]
    conf = result["confidence"]

    def names(lst):
        return ", ".join(i["name"].lower() for i in lst) or "none"

    banker = (
        f"Score {score:.2f}/100 (displayed {result['display_score']}) from {8 - len(missing)} of 8 indicators, "
        f"{result['window_start']} to {result['window_end']}. Strengths: {names(strengths)}. "
        f"Concerns: {names(concerns)}. Confidence: {conf['level']}."
    )
    if missing:
        banker += f" Not scored for lack of data: {names(missing)}."
    doing_well = [MERCHANT_SHORT[i["key"]][0] for i in strengths]
    needs_work = [MERCHANT_SHORT[i["key"]][1] for i in concerns]
    merchant = (
        f"Your business scores {result['display_score']} out of 100. "
        + (f"You are doing well on {_join(doing_well)}. " if doing_well else "")
        + (f"The biggest things holding your score back are {_join(needs_work)}." if needs_work else "No major concerns were found.")
    )
    return {
        "banker_summary": banker,
        "merchant_summary": merchant,
        "doing_well": doing_well,
        "needs_work": needs_work,
        "strengths": [i["key"] for i in strengths],
        "concerns": [i["key"] for i in concerns],
        "watch": [i["key"] for i in watch],
        "not_scored": [i["key"] for i in missing],
        "source": "template",
    }


def _join(items: list[str]) -> str:
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


DISCLAIMER = (
    "This is a prototype rules-based score built from synthetic or self-shared records. It is not a validated "
    "credit-risk model, not a credit bureau score and not a loan decision. A human loan officer makes the final decision."
)

__all__ = ["indicator_text", "summaries", "DISCLAIMER", "inr", "pct", "C"]
