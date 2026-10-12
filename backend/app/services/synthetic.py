"""Synthetic demonstration data. ALL businesses, people and transactions here are fictional.

Records are generated deterministically (fixed seeds, no randomness at import
time) so re-running the seed always produces the same data. Raj's Bakery is
constructed so that the rules engine, applied to its raw records, yields the
illustrative sub-scores from the CrediPath deck (overall 61.75). The score is
computed from these records; it is not stored anywhere as a constant.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date, timedelta

import numpy as np

SYNTHETIC_NOTE = "SYNTHETIC DEMO DATA - fictional business, not real financial information"


@dataclass
class BusinessSeed:
    id: str
    name: str
    owner_name: str
    category: str
    city: str
    years_in_operation: int
    description: str
    bureau_status: str
    conventional_view: str
    records: list[dict] = field(default_factory=list)
    # Extra as-of dates at which historical assessments are produced at seed time.
    history_as_of: list[str] = field(default_factory=list)


def _months(start: tuple[int, int], n: int) -> list[tuple[int, int]]:
    y, m = start
    out = []
    for _ in range(n):
        out.append((y, m))
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


def _d(y: int, m: int, day: int) -> date:
    return date(y, m, min(day, calendar.monthrange(y, m)[1]))


def _iso(d: date | None) -> str | None:
    return d.isoformat() if d else None


def _rec(record_type, d, amount, **kw) -> dict:
    r = {
        "record_type": record_type,
        "date": _iso(d),
        "amount": round(float(amount), 2),
        "direction": kw.get("direction"),
        "counterparty": kw.get("counterparty"),
        "category": kw.get("category"),
        "channel": kw.get("channel"),
        "reference": kw.get("reference"),
        "due_date": _iso(kw.get("due_date")),
        "paid_date": _iso(kw.get("paid_date")),
        "balance_after": kw.get("balance_after"),
        "notes": kw.get("notes"),
    }
    return r


def _orth_scale(pattern: np.ndarray, basis: list[np.ndarray], target_std: float) -> np.ndarray:
    """Make ``pattern`` orthogonal to ``basis`` vectors, then scale to target population std."""
    v = pattern.astype(float).copy()
    for b in basis:
        b = b.astype(float)
        v -= (v @ b) / (b @ b) * b
    return v / v.std() * target_std


def _split(total: int, weights: list[float]) -> list[int]:
    w = np.array(weights, dtype=float)
    parts = np.floor(total * w / w.sum()).astype(int)
    parts[-1] += total - parts.sum()
    return [int(p) for p in parts]


def _bank_ledger(events: list[dict], opening: float) -> list[dict]:
    """Sort bank events by date and attach running balances."""
    events = sorted(events, key=lambda e: (e["date"], 0 if e["direction"] == "credit" else 1))
    bal = opening
    for e in events:
        bal += e["amount"] if e["direction"] == "credit" else -e["amount"]
        e["balance_after"] = round(bal, 2)
    return events


# ---------------------------------------------------------------------------
# Raj's Bakery — primary demo record
# ---------------------------------------------------------------------------

RAJ_MONTHS = _months((2025, 9), 13)  # Sep 2025 .. Sep 2026; Sep 2026 is the "update" month
RAJ_BUFFER_DAYS = 22.0
RAJ_BLANK_PAYEE_MONTHS = 9


def _raj_series():
    n = 12
    idx = np.arange(n, dtype=float)
    mean_in = 150_000.0
    ones = np.ones(n)
    trend = 0.15 * mean_in / 12 * (idx - idx.mean())  # +15% annualised
    target_cv = 0.075
    noise_std = np.sqrt((target_cv * mean_in) ** 2 - trend.std() ** 2)
    # Bakery seasonality: festive peaks and a monsoon dip.
    pattern = np.array([1.1, 0.9, 1.6, -0.5, -0.8, -0.3, 0.1, -0.6, -1.1, -1.0, -0.2, 0.7])
    noise = _orth_scale(pattern, [ones, idx - idx.mean()], noise_std)
    inflow = mean_in + trend + noise
    # Net flow: lumpy outflows (bulk flour/sugar purchases before festivals).
    net_pattern = np.array([-1.3, 1.6, -0.9, 1.2, 0.4, -1.1, 0.9, 1.0, -0.4, 0.8, -1.5, 0.1])
    net = 2_500.0 + _orth_scale(net_pattern, [ones], 0.12 * mean_in)
    return np.round(inflow), np.round(net)


def raj_bakery(include_update: bool = False) -> tuple[BusinessSeed, list[dict]]:
    """Return (seed with baseline records, list of update-CSV records for Sep 2026)."""
    inflow, net = _raj_series()
    # September 2026 (update month): steadier month after the merchant starts acting.
    inflow = np.append(inflow, 171_400)
    net = np.append(net, 4_200)
    months = RAJ_MONTHS
    customers = ["Brew Corner Cafe", "Hotel Sai Palace", "Green Valley School Canteen"]
    suppliers = ["Shree Flour Mills", "Patil Dairy", "Kumar Packaging"]

    bank: list[dict] = []
    invoices: list[dict] = []
    sales: list[dict] = []
    supplier_ledger: list[dict] = []
    loans: list[dict] = []

    # --- Invoices (B2B credit sales), recorded from Mar 2026 ------------------
    # (month index, customer, amount, due offset days, paid offset from due date;
    #  None = unpaid at the baseline, collected during September 2026 in the update)
    inv_plan = [
        (6, 0, 9_000, 15, -2),
        (6, 1, 12_000, 15, 20),
        (7, 2, 8_000, 15, None),
        (7, 0, 9_500, 15, -1),
        (8, 1, 11_000, 15, 25),
        (9, 0, 9_000, 15, 6),
        (9, 2, 7_500, 15, None),
        (10, 1, 12_500, 15, None),
        (10, 0, 9_000, 15, 8),
        (11, 2, 9_500, 10, None),
        (11, 0, 9_500, 30, None),  # not yet due at end of Aug 2026
    ]
    collected_in_update = {3: 7, 7: 9, 8: 12, 10: 14, 11: 16}  # plan number -> day of Sep 2026
    update_paid = {}  # invoice ref -> paid date in the September update
    for n, (mi, ci, amt, due_off, paid_off) in enumerate(inv_plan, 1):
        y, m = months[mi]
        issued = _d(y, m, 6 + (n % 3) * 7)
        due = issued + timedelta(days=due_off)
        paid = due + timedelta(days=paid_off) if paid_off is not None else None
        ref = f"RB-INV-{y % 100}{m:02d}-{n:02d}"
        invoices.append({"ref": ref, "customer": customers[ci], "amount": amt, "issued": issued, "due": due, "paid": paid, "mi": mi})
        if n in collected_in_update:
            update_paid[ref] = date(2026, 9, collected_in_update[n])
    new_invoices = [
        {"ref": "RB-INV-2609-12", "customer": customers[0], "amount": 9_800, "issued": date(2026, 9, 3), "due": date(2026, 9, 18), "paid": date(2026, 9, 17), "mi": 12},
        {"ref": "RB-INV-2609-13", "customer": customers[1], "amount": 12_000, "issued": date(2026, 9, 5), "due": date(2026, 9, 20), "paid": date(2026, 9, 20), "mi": 12},
    ]

    # --- Bank ledger ----------------------------------------------------------
    emi = 15_000
    loan_ref = "MUDRA-RB-2025-0417"
    loan_principal = 172_000
    events = []
    for mi, (y, m) in enumerate(months):
        income = int(inflow[mi])
        outflow = int(inflow[mi] - net[mi])
        # Invoice receipts landing in this month.
        receipts = []
        for inv in invoices + new_invoices:
            pd_ = inv["paid"] or update_paid.get(inv["ref"])
            if pd_ and (pd_.year, pd_.month) == (y, m):
                receipts.append((pd_, inv["customer"], inv["amount"], inv["ref"]))
        rec_total = sum(r[2] for r in receipts)
        for pd_, cust, amt, ref in receipts:
            events.append({"date": pd_, "direction": "credit", "amount": amt, "counterparty": cust, "category": "invoice_receipt", "channel": "NEFT", "reference": ref})
        # UPI settlements (weekly) + one cash deposit.
        rest = income - rec_total
        upi_parts = _split(int(rest * 0.86), [1.0, 1.05, 0.95, 1.1])
        for k, amt in enumerate(upi_parts):
            events.append({"date": _d(y, m, 7 * k + 7), "direction": "credit", "amount": amt, "counterparty": "PhonePe Merchant Settlement", "category": "sales", "channel": "UPI", "reference": None})
        events.append({"date": _d(y, m, 20), "direction": "credit", "amount": rest - sum(upi_parts), "counterparty": None, "category": "sales", "channel": "cash", "reference": None})
        # Outflows.
        fixed = [
            (_d(y, m, 1), 18_000, "Deshmukh Properties", "rent", "NEFT"),
            (_d(y, m, 2), 24_000, "Staff salaries", "salary", "NEFT"),
            (_d(y, m, 11), 6_400 + 300 * (mi % 4), "MSEDCL Electricity", "utilities", "UPI"),
        ]
        emi_paid = None
        if 2 <= mi:  # EMIs from Nov 2025
            due = _d(y, m, 5)
            emi_paid = due + timedelta(days=12) if mi == 5 else due  # February 2026 paid late
            loans.append({"due": due, "paid": emi_paid, "n": mi - 1})
            fixed.append((emi_paid, emi, "Bank of Maharashtra - Mudra EMI", "loan_emi", "NACH"))
        fixed_total = sum(f[1] for f in fixed)
        supplier_total = outflow - fixed_total
        sup_parts = _split(supplier_total, [0.48, 0.32, 0.20] if mi % 3 else [0.55, 0.30, 0.15])
        sup_days = [9, 16, 24]
        for k, (amt, name) in enumerate(zip(sup_parts, suppliers)):
            d = _d(y, m, sup_days[k])
            events.append({"date": d, "direction": "debit", "amount": amt, "counterparty": name, "category": "supplier", "channel": "UPI" if k else "NEFT", "reference": None})
            supplier_ledger.append({"date": d, "amount": amt, "counterparty": name, "mi": mi, "due": d + timedelta(days=0 if k else 2)})
        for d, amt, party, cat, ch in fixed:
            events.append({"date": d, "direction": "debit", "amount": amt, "counterparty": party, "category": cat, "channel": ch, "reference": loan_ref if cat == "loan_emi" else None})
        sales.append({"date": _d(y, m, calendar.monthrange(y, m)[1]), "amount": round(income * 1.03, -2), "mi": mi})

    # Opening balance chosen so the average month-end balance over the baseline
    # year equals RAJ_BUFFER_DAYS of average outflow (a thin cash buffer).
    base_out = (inflow[:12] - net[:12]).mean()
    opening = round(RAJ_BUFFER_DAYS * base_out / 30 - np.cumsum(net[:12]).mean())
    ledger = _bank_ledger(events, opening)

    # --- Build record dicts ---------------------------------------------------
    base: list[dict] = []
    update: list[dict] = []

    # Bank: blank category on some cash deposits (data-quality gap seen in the deck).
    for e in ledger:
        mi = months.index((e["date"].year, e["date"].month))
        cat = e["category"]
        party = e["counterparty"]
        if e["channel"] == "cash" and mi % 4 == 1:
            cat = None
        # Small UPI payments to the dairy/packaging suppliers came from a personal
        # UPI handle and lack payee names in the statement for the earlier months.
        if mi < RAJ_BLANK_PAYEE_MONTHS and party in ("Patil Dairy", "Kumar Packaging"):
            party = None
        rec = _rec("bank", e["date"], e["amount"], direction=e["direction"], counterparty=party, category=cat, channel=e["channel"], reference=e["reference"], balance_after=e["balance_after"])
        (update if mi == 12 else base).append(rec)

    # Sales register: Raj kept only Jun-Aug 2026 digitally; the rest is backfilled in the update.
    for s in sales:
        rec = _rec("sale", s["date"], s["amount"], channel="UPI + cash", notes="Monthly sales total")
        (base if s["mi"] in (9, 10, 11) else update).append(rec)

    # Supplier payments ledger: only Jun-Aug 2026 shared at baseline.
    for s in supplier_ledger:
        rec = _rec("supplier_payment", s["date"], s["amount"], counterparty=s["counterparty"], due_date=s["due"], paid_date=s["date"])
        (base if s["mi"] in (9, 10, 11) else update).append(rec)

    # Invoices.
    for inv in invoices:
        base.append(_rec("invoice", inv["issued"], inv["amount"], counterparty=inv["customer"], reference=inv["ref"], due_date=inv["due"], paid_date=inv["paid"], channel="NEFT"))
        if inv["ref"] in update_paid:
            update.append(_rec("invoice", inv["issued"], inv["amount"], counterparty=inv["customer"], reference=inv["ref"], due_date=inv["due"], paid_date=update_paid[inv["ref"]], channel="NEFT", notes="Collected - payment received"))
    for inv in new_invoices:
        update.append(_rec("invoice", inv["issued"], inv["amount"], counterparty=inv["customer"], reference=inv["ref"], due_date=inv["due"], paid_date=inv["paid"], channel="NEFT"))

    # Loan repayments.
    outstanding = loan_principal
    for ln in loans:
        outstanding = max(0, outstanding - (emi - 1_400))
        rec = _rec("loan_repayment", ln["due"], emi, counterparty="Bank of Maharashtra", reference=loan_ref, paid_date=ln["paid"], channel="NACH", balance_after=outstanding)
        (update if ln["due"].month == 9 and ln["due"].year == 2026 else base).append(rec)

    seed = BusinessSeed(
        id="rajs-bakery",
        name="Raj's Bakery",
        owner_name="Raj Kulkarni (fictional)",
        category="Bakery",
        city="Pune, Maharashtra",
        years_in_operation=6,
        description="Neighbourhood bakery selling breads, cakes and snacks; supplies three cafes and a school canteen on credit.",
        bureau_status="Thin file",
        conventional_view="Bureau file shows one Mudra loan opened Oct 2025 and no other credit lines. No collateral offered. Too little history for a conventional bureau-led decision.",
        records=base,
    )
    return seed, update


# ---------------------------------------------------------------------------
# Other synthetic businesses (random-but-seeded generators)
# ---------------------------------------------------------------------------

def _generic(
    rng: np.random.Generator,
    months: list[tuple[int, int]],
    mean_in: float,
    cv: float,
    growth: float,
    net_mean: float,
    net_sd: float,
    opening: float,
    fixed: list[tuple[int, int, str, str]],
    suppliers: list[str],
    emi: int | None = None,
    emi_late: set[int] | None = None,
    emi_missed: set[int] | None = None,
    loan_ref: str | None = None,
    lender: str | None = None,
    sales_months: set[int] | None = None,
    supplier_months: set[int] | None = None,
    extra_events: list[dict] | None = None,
    blank_counterparty_every: int = 0,
):
    n = len(months)
    idx = np.arange(n)
    inflow = mean_in * (1 + growth / 12 * (idx - idx.mean())) * (1 + rng.normal(0, cv, n))
    net = net_mean + rng.normal(0, net_sd, n)
    events = []
    records = []
    emi_late = emi_late or set()
    emi_missed = emi_missed or set()
    for mi, (y, m) in enumerate(months):
        income = int(round(inflow[mi], -2))
        outflow = int(round(inflow[mi] - net[mi], -2))
        parts = _split(income, list(rng.uniform(0.8, 1.2, 4)))
        for k, amt in enumerate(parts):
            events.append({"date": _d(y, m, 7 * k + 6), "direction": "credit", "amount": amt, "counterparty": None if blank_counterparty_every and (mi + k) % blank_counterparty_every == 0 else "UPI Settlement - Paytm", "category": "sales", "channel": "UPI", "reference": None})
        fx = [(_d(y, m, day), amt, party, cat) for day, amt, party, cat in fixed]
        if emi:
            due = _d(y, m, 7)
            if mi in emi_missed:
                paid = None
            else:
                paid = due + timedelta(days=14) if mi in emi_late else due
            records.append(_rec("loan_repayment", due, emi, counterparty=lender, reference=loan_ref, paid_date=paid, channel="NACH"))
            if paid:
                fx.append((paid, emi, lender, "loan_emi"))
        sup_total = outflow - sum(f[1] for f in fx)
        sp = _split(max(sup_total, 1000), list(rng.uniform(0.6, 1.4, len(suppliers))))
        for k, (amt, name) in enumerate(zip(sp, suppliers)):
            d = _d(y, m, 4 + k * 8)
            events.append({"date": d, "direction": "debit", "amount": amt, "counterparty": name, "category": "supplier", "channel": "NEFT", "reference": None})
            if supplier_months is None or mi in supplier_months:
                records.append(_rec("supplier_payment", d, amt, counterparty=name, due_date=d + timedelta(days=3), paid_date=d))
        for d, amt, party, cat in fx:
            events.append({"date": d, "direction": "debit", "amount": amt, "counterparty": party, "category": cat, "channel": "NEFT", "reference": loan_ref if cat == "loan_emi" else None})
        if sales_months is None or mi in sales_months:
            records.append(_rec("sale", _d(y, m, 28), round(income * float(rng.uniform(0.97, 1.06)), -2), channel="UPI + cash", notes="Monthly sales total"))
    events += extra_events or []
    for e in _bank_ledger(events, opening):
        records.append(_rec("bank", e["date"], e["amount"], direction=e["direction"], counterparty=e["counterparty"], category=e["category"], channel=e["channel"], reference=e["reference"], balance_after=e["balance_after"]))
    return records


def meena_store() -> BusinessSeed:
    rng = np.random.default_rng(20251)
    months = _months((2024, 10), 24)  # 24 months -> same-month YoY growth
    records = _generic(
        rng, months, mean_in=310_000, cv=0.04, growth=0.10, net_mean=24_000, net_sd=7_000, opening=260_000,
        fixed=[(1, 22_000, "Joshi Estates", "rent"), (3, 36_000, "Staff salaries", "salary"), (12, 9_500, "MSEDCL Electricity", "utilities")],
        suppliers=["Hindustan Unilever Distributor", "Nashik Grain Traders", "Amul Parlour Supply"],
        emi=21_000, emi_late={9}, loan_ref="SIDBI-MGS-2023-0981", lender="Saraswat Co-op Bank",
    )
    return BusinessSeed(
        id="meena-general-store",
        name="Meena General Store",
        owner_name="Meena Patil (fictional)",
        category="Kirana / grocery",
        city="Nashik, Maharashtra",
        years_in_operation=11,
        description="Family-run kirana with home delivery; mostly UPI and cash sales, no credit sales.",
        bureau_status="Thin file",
        conventional_view="One working-capital loan with a co-operative bank (24 months). No credit card, no collateral beyond stock.",
        records=records,
        history_as_of=["2026-07-31", "2026-08-31"],
    )


def sharma_electronics() -> BusinessSeed:
    rng = np.random.default_rng(77)
    months = _months((2025, 10), 12)
    extra = [
        # Round-trip with a related party (should raise a circular-flow flag).
        {"date": date(2026, 3, 10), "direction": "debit", "amount": 120_000, "counterparty": "Vikas Traders", "category": "other", "channel": "IMPS", "reference": None},
        {"date": date(2026, 3, 16), "direction": "credit", "amount": 118_500, "counterparty": "Vikas Traders", "category": "sales", "channel": "IMPS", "reference": None},
        # One-off bulk order (should raise a spike flag).
        {"date": date(2026, 6, 21), "direction": "credit", "amount": 285_000, "counterparty": "Apex Infra Pvt Ltd", "category": "sales", "channel": "NEFT", "reference": None},
    ]
    records = _generic(
        rng, months, mean_in=240_000, cv=0.16, growth=-0.05, net_mean=-2_000, net_sd=30_000, opening=70_000,
        fixed=[(1, 30_000, "Malwa Mall Pvt Ltd", "rent"), (3, 28_000, "Staff salaries", "salary")],
        suppliers=["Sunrise Mobiles Distribution", "Redington Distribution"],
        emi=46_000, emi_late={2, 6, 9}, emi_missed={10}, loan_ref="NBFC-SME-55102", lender="QuickGrow Finance (NBFC)",
        sales_months=set(range(0, 12, 2)), supplier_months={8, 9, 10, 11},
        extra_events=extra,
    )
    # A paid invoice whose payment never shows in the bank (record mismatch).
    records.append(_rec("invoice", date(2026, 7, 2), 42_000, counterparty="City Coaching Centre", reference="SME-INV-0712", due_date=date(2026, 7, 17), paid_date=date(2026, 7, 16), channel="NEFT"))
    records.append(_rec("invoice", date(2026, 8, 4), 36_000, counterparty="City Coaching Centre", reference="SME-INV-0804", due_date=date(2026, 8, 19), paid_date=None, channel="NEFT"))
    return BusinessSeed(
        id="sharma-mobile-electronics",
        name="Sharma Mobile & Electronics",
        owner_name="Anil Sharma (fictional)",
        category="Electronics retail",
        city="Indore, Madhya Pradesh",
        years_in_operation=4,
        description="Mobile phone and accessories retailer with occasional bulk orders from institutions.",
        bureau_status="Limited history",
        conventional_view="One NBFC business loan with recent late payments reported. No collateral.",
        records=records,
    )


def green_leaf_tiffin() -> BusinessSeed:
    rng = np.random.default_rng(5)
    months = _months((2026, 5), 5)  # only 5 months of data -> low confidence
    records = _generic(
        rng, months, mean_in=95_000, cv=0.07, growth=0.2, net_mean=9_000, net_sd=5_000, opening=38_000,
        fixed=[(2, 9_000, "Kitchen rent - Mrs. Nair", "rent"), (4, 18_000, "Cook and delivery staff", "salary")],
        suppliers=["Thane Vegetable Market", "Annapurna Grocers"],
        sales_months=set(), supplier_months=set(), blank_counterparty_every=3,
    )
    return BusinessSeed(
        id="green-leaf-tiffin",
        name="Green Leaf Tiffin Services",
        owner_name="Lata Nair (fictional)",
        category="Food services",
        city="Thane, Maharashtra",
        years_in_operation=1,
        description="Home-style tiffin subscriptions for office workers, paid monthly via UPI.",
        bureau_status="New to credit",
        conventional_view="No bureau record. New-to-credit applicant; conventional assessment cannot score this business.",
        records=records,
    )


def all_businesses() -> list[BusinessSeed]:
    raj, _ = raj_bakery()
    return [raj, meena_store(), sharma_electronics(), green_leaf_tiffin()]


# ---------------------------------------------------------------------------
# Downloadable sample files
# ---------------------------------------------------------------------------

def new_business_sample() -> list[dict]:
    """12 months of complete records for a fictional new applicant (used with 'Add a business')."""
    rng = np.random.default_rng(314)
    months = _months((2025, 9), 12)
    records = _generic(
        rng, months, mean_in=180_000, cv=0.06, growth=0.08, net_mean=11_000, net_sd=9_000, opening=90_000,
        fixed=[(1, 15_000, "Shivaji Nagar Market Committee", "rent"), (3, 22_000, "Staff salaries", "salary"), (10, 5_200, "MSEDCL Electricity", "utilities")],
        suppliers=["Konkan Fruit Wholesale", "Sahyadri Farms Supply"],
        emi=12_000, emi_late={4}, loan_ref="SBI-SME-2025-7731", lender="State Bank of India",
    )
    customers = ["Hotel Annapurna", "Sunshine Juice Bar"]
    for mi, (y, m) in enumerate(months):
        if mi % 2:
            continue
        issued = _d(y, m, 8)
        due = issued + timedelta(days=15)
        paid = None if mi == 10 else due + timedelta(days=(9 if mi == 4 else -1))
        amt = 14_000 + 500 * mi
        cust = customers[(mi // 2) % 2]
        records.append(_rec("invoice", issued, amt, counterparty=cust, reference=f"FF-{y % 100}{m:02d}-{mi + 1:02d}", due_date=due, paid_date=paid, channel="NEFT"))
        if paid:
            records.append(_rec("bank", paid, amt, direction="credit", counterparty=cust, category="invoice_receipt", channel="NEFT", reference=f"FF-{y % 100}{m:02d}-{mi + 1:02d}"))
    return records


def template_rows() -> list[dict]:
    return [
        _rec("bank", date(2026, 8, 7), 31_250, direction="credit", counterparty="PhonePe Merchant Settlement", category="sales", channel="UPI", balance_after=1_02_400),
        _rec("bank", date(2026, 8, 9), 18_400, direction="debit", counterparty="Shree Flour Mills", category="supplier", channel="NEFT", balance_after=84_000),
        _rec("sale", date(2026, 8, 31), 1_52_000, channel="UPI + cash", notes="Monthly sales total"),
        _rec("invoice", date(2026, 8, 6), 9_000, counterparty="Brew Corner Cafe", reference="INV-0801", due_date=date(2026, 8, 21), paid_date=date(2026, 8, 20), channel="NEFT"),
        _rec("supplier_payment", date(2026, 8, 9), 18_400, counterparty="Shree Flour Mills", due_date=date(2026, 8, 11), paid_date=date(2026, 8, 9)),
        _rec("loan_repayment", date(2026, 8, 5), 15_000, counterparty="Bank of Maharashtra", reference="MUDRA-0001", paid_date=date(2026, 8, 5), channel="NACH", balance_after=45_000),
    ]


def invalid_example_csv() -> str:
    return "\n".join(
        [
            "record_type,date,amount,direction,counterparty,category,channel,reference,due_date,paid_date,balance_after,notes",
            "bank,2026-08-07,31250,credit,PhonePe Merchant Settlement,sales,UPI,,,,102400,valid row",
            "bank,2026-08-08,-5000,debit,Patil Dairy,supplier,UPI,,,,97400,negative amount",
            "bank,2026-08-09,12000,,Kumar Packaging,supplier,UPI,,,,85400,missing direction",
            "invoice,2026-08-10,9000,,Brew Corner Cafe,,NEFT,INV-1,,,,missing due date",
            "invoice,2026-08-10,9000,,Hotel Sai Palace,,NEFT,INV-2,2026-08-01,,,due date before invoice date",
            "sale,31/13/2026,150000,,,,UPI,,,,,impossible date",
            "receipt,2026-08-12,4000,,,,,,,,,unknown record type",
            "sale,2026-08-31,abc,,,,UPI,,,,,amount not a number",
            "supplier_payment,2026-08-15,8000,,,,,,,,,missing supplier name",
            "loan_repayment,2026-08-05,15000,,Bank of Maharashtra,,NACH,MUDRA-0001,,2026-08-05,,valid row",
            "bank,2026-08-20,21000,credit,,,cash,,,,,valid but missing recommended fields",
        ]
    ) + "\n"
