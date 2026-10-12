import math

import pandas as pd
import pytest

from app.scoring import config as C
from app.scoring.engine import band, compute_overall, round_half_up, score_records, to_frame
from app.scoring.quality import run_checks
from app.scoring.recommend import build_plan, what_if
from app.services.synthetic import all_businesses, raj_bakery

PPT_SUBSCORES = {
    "cash_flow_stability": 50,
    "revenue_consistency": 85,
    "repayment_record": 80,
    "debt_burden": 60,
    "invoice_collection": 40,
    "liquidity_resilience": 55,
    "data_completeness": 50,
    "growth_seasonality": 70,
}


def test_weights_match_deck_and_sum_to_100():
    weights = {i.key: i.weight for i in C.INDICATORS}
    assert weights == {
        "cash_flow_stability": 0.20,
        "revenue_consistency": 0.15,
        "repayment_record": 0.15,
        "debt_burden": 0.15,
        "invoice_collection": 0.10,
        "liquidity_resilience": 0.10,
        "data_completeness": 0.10,
        "growth_seasonality": 0.05,
    }
    assert math.isclose(sum(weights.values()), 1.0)


def test_formula_reproduces_deck_example():
    out = compute_overall(PPT_SUBSCORES)
    assert out["overall"] == 61.75
    assert out["display"] == 62
    contrib = {r["key"]: r["contribution"] for r in out["indicators"]}
    assert contrib["cash_flow_stability"] == 10.0
    assert contrib["revenue_consistency"] == 12.75
    assert contrib["growth_seasonality"] == 3.5


def test_raj_bakery_scored_from_raw_records():
    seed, _ = raj_bakery()
    result = score_records(to_frame(seed.records))
    subs = {i["key"]: i["sub_score"] for i in result["indicators"]}
    assert subs == PPT_SUBSCORES
    assert result["overall_score"] == 61.75
    assert result["display_score"] == 62
    # Monthly sales of about Rs 1.5 lakh.
    assert round(result["monthly"].inflow.mean(), -3) == 150_000


def test_raj_strengths_concerns_and_verification():
    seed, _ = raj_bakery()
    df = to_frame(seed.records)
    r = score_records(df)
    bands = {i["key"]: i["band"] for i in r["indicators"]}
    assert bands["revenue_consistency"] == "strength"
    assert bands["repayment_record"] == "strength"
    assert bands["cash_flow_stability"] == "concern"
    assert bands["invoice_collection"] == "concern"
    flags = run_checks(df, r["window"], r["monthly"], r["indicators"], r["confidence"])
    kinds = {f["kind"] for f in flags}
    assert "overdue_receivables" in kinds
    assert "circular_flow" not in kinds and "one_off_spike" not in kinds


def test_raj_plan_and_what_if_match_deck():
    seed, _ = raj_bakery()
    r = score_records(to_frame(seed.records))
    plan = build_plan(r["indicators"])
    top = [p["action_key"] for p in plan if p["in_top_plan"]]
    assert top == ["collect_overdue_invoices", "complete_records", "stabilise_cash_flow"]
    impacts = {p["action_key"]: p["expected_impact"] for p in plan}
    assert impacts == {"collect_overdue_invoices": 3.5, "complete_records": 3.5, "stabilise_cash_flow": 3.0, "build_cash_buffer": 1.0}
    wi = what_if(r["indicators"], plan, list(impacts))
    assert wi["baseline_display"] == 62 and wi["hypothetical_display"] == 73
    assert wi["hypothetical"] is True
    assert [s["delta"] for s in wi["steps"]] == [3.5, 3.5, 3.0, 1.0]


def test_what_if_does_not_mutate_inputs():
    seed, _ = raj_bakery()
    r = score_records(to_frame(seed.records))
    before = [i["sub_score"] for i in r["indicators"]]
    what_if(r["indicators"], build_plan(r["indicators"]), ["collect_overdue_invoices"])
    assert [i["sub_score"] for i in r["indicators"]] == before


def test_missing_indicator_is_excluded_not_zero():
    subs = dict(PPT_SUBSCORES, repayment_record=None)
    out = compute_overall(subs)
    zero = compute_overall(dict(PPT_SUBSCORES, repayment_record=0))
    # Re-normalised over 85% of the weight, so higher than scoring the gap as zero.
    expected = (61.75 - 0.15 * 80) / 0.85
    assert out["overall"] == round(expected, 2)
    assert out["overall"] > zero["overall"]
    eff = {r["key"]: r["effective_weight"] for r in out["indicators"]}
    assert eff["repayment_record"] == 0
    assert math.isclose(sum(eff.values()), 1.0, abs_tol=1e-5)


def test_no_scored_indicators_returns_none():
    out = compute_overall({k: None for k in PPT_SUBSCORES})
    assert out["overall"] is None and out["display"] is None


def test_bands_and_rounding():
    assert band(None) == "insufficient_data"
    assert band(75) == "strength" and band(74) == "watch" and band(55) == "watch" and band(54.9) == "concern"
    assert round_half_up(61.75) == 62 and round_half_up(61.5) == 62 and round_half_up(61.49) == 61


def _bank(d, amt, direction, bal=None, cat="sales", cp="UPI"):
    return {"record_type": "bank", "date": d, "amount": amt, "direction": direction, "balance_after": bal, "category": cat, "counterparty": cp}


def test_missing_months_are_nan_not_zero():
    recs = []
    for m in (1, 2, 3, 6, 7, 8):  # Apr and May missing
        recs.append(_bank(f"2026-{m:02d}-10", 100_000, "credit", 50_000))
        recs.append(_bank(f"2026-{m:02d}-15", 90_000, "debit", 60_000, cat="supplier", cp="S"))
    r = score_records(to_frame(recs))
    ms = r["monthly"]
    assert pd.isna(ms.loc[pd.Period("2026-04", "M"), "inflow"])
    # Revenue is perfectly steady across the months that do exist.
    rev = next(i for i in r["indicators"] if i["key"] == "revenue_consistency")
    assert rev["sub_score"] == 100
    comp = next(i for i in r["indicators"] if i["key"] == "data_completeness")
    assert "2026-04" in comp["details"]["coverage"]["bank"]["missing_months"]


def test_thin_data_is_low_confidence_and_unscored():
    recs = [_bank("2026-08-05", 50_000, "credit", 20_000), _bank("2026-08-20", 40_000, "debit", 10_000, cat="rent", cp="L")]
    r = score_records(to_frame(recs))
    statuses = {i["key"]: i["status"] for i in r["indicators"]}
    assert statuses["cash_flow_stability"] == "insufficient_data"
    assert statuses["repayment_record"] == "insufficient_data"
    assert r["confidence"]["level"] == "low"


def test_repayment_grace_and_open_instalments():
    recs = [_bank(f"2026-{m:02d}-01", 100_000, "credit", 10_000) for m in range(1, 9)]
    for m in range(1, 9):
        paid = f"2026-{m:02d}-08" if m != 3 else "2026-03-20"  # 3 days late = on time (grace 5); March 15 days late
        recs.append({"record_type": "loan_repayment", "date": f"2026-{m:02d}-05", "amount": 5000, "reference": "L1", "paid_date": paid})
    recs.append({"record_type": "loan_repayment", "date": "2026-08-30", "amount": 5000, "reference": "L1", "paid_date": None})
    r = score_records(to_frame(recs), pd.Timestamp("2026-08-31"))
    rep = next(i for i in r["indicators"] if i["key"] == "repayment_record")
    # 8 instalments counted (the one due Aug 30 is still within grace), 7 on time.
    assert rep["details"]["instalments"] == 8
    assert rep["details"]["on_time"] == 7
    assert rep["sub_score"] == round_half_up(((7 / 8) - 0.5) / 0.5 * 100)


def test_circular_flow_and_spike_detected_for_sharma():
    sharma = [b for b in all_businesses() if b.id == "sharma-mobile-electronics"][0]
    df = to_frame(sharma.records)
    r = score_records(df)
    kinds = [f["kind"] for f in run_checks(df, r["window"], r["monthly"], r["indicators"], r["confidence"])]
    assert "circular_flow" in kinds
    assert "one_off_spike" in kinds
    assert "record_mismatch" in kinds


def test_scoring_is_deterministic():
    seed, _ = raj_bakery()
    a = score_records(to_frame(seed.records))
    b = score_records(to_frame(list(reversed(seed.records))))
    assert a["overall_score"] == b["overall_score"]


@pytest.mark.parametrize("biz", all_businesses(), ids=lambda b: b.id)
def test_every_seed_scores_within_range(biz):
    r = score_records(to_frame(biz.records))
    assert r["overall_score"] is not None and 0 <= r["overall_score"] <= 100
    for i in r["indicators"]:
        assert i["sub_score"] is None or 0 <= i["sub_score"] <= 100


def _conf(biz_id):
    biz = [b for b in all_businesses() if b.id == biz_id][0]
    return score_records(to_frame(biz.records))["confidence"]


def test_confidence_levels_and_reasons():
    raj = _conf("rajs-bakery")
    assert raj["level"] == "medium"
    status = {c["key"]: c["status"] for c in raj["checks"]}
    assert status == {"bank_months": "pass", "completeness": "warn", "missing_indicators": "pass"}
    # A cash/UPI-only shop has no invoices: not applicable, not a gap.
    meena = _conf("meena-general-store")
    assert meena["level"] == "high"
    assert "not applicable: invoice collection" in meena["checks"][2]["value"]
    tiffin = _conf("green-leaf-tiffin")
    assert tiffin["level"] == "low"
    assert {c["key"] for c in tiffin["checks"] if c["status"] == "fail"} >= {"bank_months", "completeness"}
