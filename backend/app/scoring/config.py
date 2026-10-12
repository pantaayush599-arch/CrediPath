"""Scoring configuration for the CrediPath rules engine.

Everything that shapes a score lives here: indicator weights, the
piecewise-linear thresholds that turn a raw metric into a 0-100 sub-score,
and the benchmark each indicator is compared against when building the
improvement plan. These are *prototype* thresholds. They have not been
back-tested against repayment outcomes and must be recalibrated before any
real lending use.
"""

from __future__ import annotations

from dataclasses import dataclass, field

SCORING_VERSION = "rules-v1.0"

# Sub-score bands used for labelling (strength / watch / concern).
STRENGTH_MIN = 75
CONCERN_BELOW = 55


@dataclass(frozen=True)
class IndicatorConfig:
    key: str
    name: str
    weight: float  # share of the overall score, 0-1
    metric_label: str
    metric_unit: str
    # Piecewise-linear mapping: list of (metric_value, sub_score) points with
    # increasing metric values. Values outside the range are clamped.
    thresholds: list[tuple[float, float]]
    # Sub-score at which the indicator is considered healthy. Indicators below
    # their benchmark become candidate improvement actions.
    benchmark: float
    description: str
    higher_metric_is_better: bool = True
    rule_text: str = ""
    extra: dict = field(default_factory=dict)


INDICATORS: list[IndicatorConfig] = [
    IndicatorConfig(
        key="cash_flow_stability",
        name="Cash-flow stability",
        weight=0.20,
        metric_label="Monthly net cash-flow swing (std. dev. as % of avg. monthly income)",
        metric_unit="ratio",
        thresholds=[(0.02, 100.0), (0.22, 0.0)],
        benchmark=65,
        higher_metric_is_better=False,
        description="How steady the money left over each month is, after all payments.",
        rule_text="Swing of 2% or less scores 100; 22% or more scores 0; linear in between.",
    ),
    IndicatorConfig(
        key="revenue_consistency",
        name="Revenue consistency",
        weight=0.15,
        metric_label="Coefficient of variation of monthly business income",
        metric_unit="ratio",
        thresholds=[(0.03, 100.0), (0.33, 0.0)],
        benchmark=85,
        higher_metric_is_better=False,
        description="How regular monthly sales receipts are.",
        rule_text="Variation of 3% or less scores 100; 33% or more scores 0; linear in between.",
    ),
    IndicatorConfig(
        key="repayment_record",
        name="Repayment record",
        weight=0.15,
        metric_label="Share of loan instalments paid within 5 days of due date",
        metric_unit="share",
        thresholds=[(0.5, 0.0), (1.0, 100.0)],
        benchmark=80,
        description="Whether loan instalments are paid on time.",
        rule_text="100% on time scores 100; 50% or less scores 0; linear in between. Grace period 5 days.",
        extra={"grace_days": 5, "min_instalments": 3},
    ),
    IndicatorConfig(
        key="debt_burden",
        name="Debt burden",
        weight=0.15,
        metric_label="Monthly debt service as % of avg. monthly income",
        metric_unit="ratio",
        thresholds=[(0.0, 100.0), (0.25, 0.0)],
        benchmark=60,
        higher_metric_is_better=False,
        description="How much of monthly income goes to loan instalments.",
        rule_text="No observed debt service scores 100; 25% of income or more scores 0; linear in between.",
    ),
    IndicatorConfig(
        key="invoice_collection",
        name="Invoice collection",
        weight=0.10,
        metric_label="Blend of on-time collection share and overdue share (by value)",
        metric_unit="share",
        thresholds=[(0.0, 0.0), (1.0, 100.0)],
        benchmark=75,
        description="How quickly customers who buy on credit pay their invoices.",
        rule_text="0.5 x (value collected by due date) + 0.5 x (1 - value still overdue), over invoices already due.",
    ),
    IndicatorConfig(
        key="liquidity_resilience",
        name="Liquidity & resilience",
        weight=0.10,
        metric_label="Cash buffer: avg. month-end balance in days of outflow",
        metric_unit="days",
        thresholds=[(0.0, 0.0), (40.0, 100.0)],
        benchmark=65,
        description="How many days the business could keep paying its bills from its bank balance.",
        rule_text="40 or more days of cover scores 100; 0 days scores 0; linear in between.",
    ),
    IndicatorConfig(
        key="data_completeness",
        name="Data completeness",
        weight=0.10,
        metric_label="Monthly record coverage x share of rows with key fields filled",
        metric_unit="share",
        thresholds=[(0.0, 0.0), (1.0, 100.0)],
        benchmark=85,
        description="How complete the shared records are across the assessment window.",
        rule_text=(
            "Coverage = months with records / expected months, averaged over bank, sales and supplier "
            "records (always expected) plus invoices and loans (expected once they appear). "
            "Multiplied by the share of rows with all recommended fields."
        ),
    ),
    IndicatorConfig(
        key="growth_seasonality",
        name="Growth & seasonality",
        weight=0.05,
        metric_label="Annualised income growth (same-month YoY if 24+ months, else trend)",
        metric_unit="ratio",
        thresholds=[(-0.20, 0.0), (0.30, 100.0)],
        benchmark=70,
        description="Whether income is growing, comparing like-for-like seasons where possible.",
        rule_text="-20% a year or worse scores 0; +30% a year or better scores 100; linear in between.",
        extra={"min_months": 6},
    ),
]

INDICATOR_BY_KEY = {i.key: i for i in INDICATORS}

# Assessment window, in calendar months, ending with the month of the latest record.
WINDOW_MONTHS = 12
MIN_MONTHS_FOR_VOLATILITY = 3

# Record categories counted for completeness.
CORE_RECORD_TYPES = ["bank", "sale", "supplier_payment"]
OPTIONAL_RECORD_TYPES = ["invoice", "loan_repayment"]

# Bank credits with these categories are not business income.
NON_INCOME_CREDIT_CATEGORIES = {"loan_disbursal", "owner_capital", "internal_transfer", "refund"}

# Anomaly detection parameters.
ANOMALY = {
    "circular_window_days": 10,
    "circular_amount_tolerance": 0.05,
    "circular_min_amount": 10_000,
    "spike_share_of_month": 0.25,
    "spike_multiple_of_median": 4.0,
    "match_window_days": 5,
    "match_amount_tolerance": 0.01,
    "sales_vs_bank_tolerance": 0.20,
}

# Improvement-plan priority used to break ties between equal impacts.
ACTION_PRIORITY = [
    "invoice_collection",
    "data_completeness",
    "cash_flow_stability",
    "liquidity_resilience",
    "debt_burden",
    "repayment_record",
    "revenue_consistency",
    "growth_seasonality",
]
PLAN_SIZE = 3


def validate_config() -> None:
    total = round(sum(i.weight for i in INDICATORS), 9)
    if total != 1.0:
        raise ValueError(f"Indicator weights must sum to 100%, got {total * 100:.2f}%")
    for ind in INDICATORS:
        xs = [p[0] for p in ind.thresholds]
        if xs != sorted(xs):
            raise ValueError(f"Thresholds for {ind.key} must have increasing metric values")


validate_config()


def config_as_dict() -> dict:
    return {
        "version": SCORING_VERSION,
        "window_months": WINDOW_MONTHS,
        "formula": "Overall score = sum(sub-score x weight); weights of indicators without enough data are re-normalised over the scored indicators.",
        "bands": {"strength_min": STRENGTH_MIN, "concern_below": CONCERN_BELOW},
        "indicators": [
            {
                "key": i.key,
                "name": i.name,
                "weight": i.weight,
                "metric_label": i.metric_label,
                "thresholds": [list(p) for p in i.thresholds],
                "benchmark": i.benchmark,
                "description": i.description,
                "rule": i.rule_text,
            }
            for i in INDICATORS
        ],
        "anomaly_rules": ANOMALY,
    }
