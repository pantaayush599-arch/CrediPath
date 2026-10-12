# CrediPath

**Credit visibility for banks, a clear path forward for MSMEs.**

CrediPath is a hackathon prototype (Hack On Track, FinTech) that turns consented business and cash-flow records into one explainable, rules-based credit score for thin-file MSMEs. The same assessment drives two dashboards:

- **Lender (banker) view.** Score and the factors behind it, strengths and concerns, risk and anomaly flags, what to verify, the conventional thin-file view alongside the evidence, and assessment history. A human makes the final decision.
- **Business-owner (merchant) view.** Plain-language findings, the top 3 ranked fixes, a what-if simulator, progress tracking, and reassessment from new records.

The loop is **Assess → Explain → Improve → Reassess**.

> All businesses, people and transactions in this repository are **synthetic**. The score is a prototype. It is **not** a validated credit-risk model, a bureau score or a loan decision.

---

## Quick start

Requirements: **Python 3.11+** (tested on 3.13) and **Node.js 20+** (tested on 22).

```bash
# 1. Backend (FastAPI on :8000)
cd backend
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt   # runtime deps + pytest
uvicorn app.main:app --port 8000   # creates the SQLite DB and seeds the demo on first start

# 2. Frontend (Next.js on :3000), in a second terminal
cd frontend
npm install
npm run dev                        # or: npm run build && npm start
```

Open **http://localhost:3000**. The frontend proxies `/api/*` to the backend (`BACKEND_URL`, default `http://127.0.0.1:8000`). API docs are at **http://localhost:8000/docs**.

On macOS/Linux, `./dev.sh` runs both servers after the installs above.

No API keys, paid services or external financial integrations are needed.

## Judging demo (about 5 minutes)

1. **Overview** (`/`). The loop, Raj's Bakery at **62/100** (61.75 exact) and the demo businesses.
2. **Lender view** (`/banker/rajs-bakery`).
   - Strengths: revenue consistency 85, repayment record 80.
   - Concerns: cash-flow stability 50, invoice collection 40, data completeness 50.
   - Verify: 4 overdue receivables worth ₹37,500.
   - The indicator table shows weight × sub-score = points, and the points add up to **61.75**. Click a row to see the raw metric.
   - The conventional bureau view ("thin file") sits next to the evidence.
3. **Owner view** (`/merchant/rajs-bakery`).
   - Plain-language summary and the top 3 fixes: collect overdue invoices **+3.5**, complete records **+3.5**, stabilise cash flow **+3.0**.
   - The what-if simulator opens on the deck scenario (top 3 + cash buffer **+1.0**): **62 → 73**, labelled hypothetical.
   - Mark a fix "Done", reload, and the progress is still saved. The score does not change.
4. **Records & reassessment** (`/merchant/rajs-bakery/records`).
   - Upload `invalid_example.csv` to see row-level errors and warnings. Nothing is stored until you confirm.
   - Upload `raj_bakery_update_sep2026.csv` (download links are on the page). It adds 62 new rows, updates 5 invoices to collected, and rescores: **61.75 → 69.50**.
   - A before/after table shows indicator changes and the flags that cleared, including the overdue receivables.
5. Back in the **lender view**, the applicant shows the updated profile, the history chart and the latest change.
6. Optional extras:
   - **Sharma Mobile & Electronics** shows circular-flow, spike and mismatch flags.
   - **Green Leaf Tiffin** is new to credit (low confidence; indicators left unscored rather than zeroed).
   - **Add a business** onboards a new profile with `new_business_sample.csv`.
   - The **theme toggle** (top right) switches light/dark/system.
7. **Overview → Restore demo data…** (with a confirmation step) puts everything back.

## How the score works

`Overall = Σ (sub-score × weight)`, on a 0–100 scale. Each sub-score maps a raw metric to 0–100 with configurable piecewise-linear thresholds (`backend/app/scoring/config.py`). The thresholds are prototype values that have not been back-tested.

| Indicator | Weight | Raw metric (12-month window) | Raj's Bakery |
|---|---:|---|---:|
| Cash-flow stability | 20% | std. dev. of monthly net cash flow ÷ avg. monthly income | 50 |
| Revenue consistency | 15% | coefficient of variation of monthly business income | 85 |
| Repayment record | 15% | share of EMIs paid within 5 days of due date | 80 |
| Debt burden | 15% | monthly debt service ÷ avg. monthly income | 60 |
| Invoice collection | 10% | 0.5 × on-time share + 0.5 × (1 − overdue share), by value | 40 |
| Liquidity & resilience | 10% | avg. month-end balance in days of outflow | 55 |
| Data completeness | 10% | monthly coverage of record types × share of rows with key fields | 50 |
| Growth & seasonality | 5% | same-month YoY growth if ≥ 24 months, else annualised trend | 70 |
| **Overall** | **100%** | | **61.75 → 62** |

- **Raj's sub-scores are calculated, not stored.** The seed generator builds Raj's raw transactions so that the engine produces the deck's values. `tests/test_scoring.py` checks this.
- **Missing data is never scored as zero.**
  - Months without records are gaps (NaN).
  - An indicator without enough evidence is marked *not scored*, and the other weights are re-normalised.
  - The gap shows up through data completeness and the flags.
- **Recommendations and the what-if** use the same `compute_overall` function. Each action lifts one indicator to its benchmark, for example invoice collection 40 → 75, which is 10% × 35 = **+3.5**. That is how the deck's +3.5 / +3.5 / +3.0 / +1.0 and **62 → 73** are reproduced. These numbers are hypothetical and are never saved as an assessment.
- **Flags prompt human review. They are not findings of fraud.** The checks cover:
  - missing months and blank fields
  - circular flows (money sent to and received back from the same party within 10 days)
  - one-off credit spikes
  - paid invoices or supplier payments with no matching bank entry
  - sales register vs. bank income gaps
  - overdue receivables and late EMIs

## Confidence (high / medium / low)

Confidence says how much evidence sits behind a score, not whether the score is good. Each assessment runs three checks:

| Check | Pass | Warning | Fail |
|---|---|---|---|
| Bank / UPI history in the 12-month window | 9+ months | 6–8 | fewer than 6 |
| Record completeness (data-completeness sub-score) | 75+ | 40–74 | below 40 |
| Applicable indicators that could not be scored | none | 1–2 | more than 2 |

**High** = all three pass, **medium** = at least one warning, **low** = any check fails. An indicator that does not apply (invoice collection for a cash/UPI-only shop) is not counted as missing. The checks and their values are shown next to every confidence label: "Why?" on the portfolio, a panel on the assessment page, and "How sure is this score?" on the owner page. Thresholds live in `CONFIDENCE_RULES` in `backend/app/scoring/config.py`.

## CSV format

```
record_type,date,amount,direction,counterparty,category,channel,reference,due_date,paid_date,balance_after,notes
```

| record_type | Required (beyond date, amount) | Recommended |
|---|---|---|
| `bank` | `direction` (credit/debit) | counterparty, category, balance_after |
| `sale` | — | channel |
| `invoice` | counterparty, due_date | reference (used to update the invoice later) |
| `supplier_payment` | counterparty | due_date |
| `loan_repayment` | reference (loan ID); `date` = due date | paid_date (blank = unpaid), balance_after |

- Dates may be `YYYY-MM-DD`, `DD-MM-YYYY` or `DD/MM/YYYY`.
- Amounts must be positive; `₹` and commas are accepted.
- Invoices and EMIs are **upserted by reference**, so uploading a later paid date updates the row. Other rows are de-duplicated, and re-uploading the same file changes nothing.

Sample files are in `backend/data/samples/` and can also be downloaded in the app:

| File | Use |
|---|---|
| `raj_bakery_update_sep2026.csv` | Reassessment demo for Raj's Bakery |
| `new_business_sample.csv` | Onboarding a new business |
| `credipath_template.csv` | One example row of each type |
| `invalid_example.csv` | Validation errors and warnings |
| `raj_bakery_baseline.csv` | Raj's seeded records, for reference |

## Database

| | |
|---|---|
| Default | SQLite at `backend/data/credipath.db`, created and seeded automatically on first start |
| Supabase / PostgreSQL | set `DATABASE_URL` (see `backend/.env.example`), e.g. `postgresql://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres`. Tables are created on startup; `backend/db/schema_postgres.sql` has the DDL if you prefer the Supabase SQL editor |

The tables are `businesses`, `financial_records`, `uploads`, `assessments`, `indicator_scores`, `risk_flags`, `recommendations` and `action_progress`, with foreign keys, check constraints, unique keys for de-duplication, and indexes.

```bash
cd backend
python -m scripts.manage seed      # idempotent: inserts only missing demo businesses
python -m scripts.manage reset     # wipe everything and restore the original demo state
python -m scripts.manage samples   # regenerate the sample CSVs
python -m scripts.manage schema    # print PostgreSQL DDL
```

You can also reset from the app: **Overview → Restore demo data…**, or call `POST /api/demo/reset?confirm=true`.

The PostgreSQL path was tested against a local PostgreSQL 16 server (the full test suite passes). It has not been run against a live Supabase project.

## Tests

```bash
cd backend && source .venv/bin/activate
python -m pytest -q                                       # 36 tests, temporary SQLite DB
DATABASE_URL=postgresql://user:pass@localhost/db python -m pytest -q   # same suite on PostgreSQL

cd frontend && npm run typecheck && npm run build
```

The tests cover:
- weights summing to 100%
- the 61.75 example, both from the formula and from Raj's raw records
- strengths, concerns and flags
- plan impacts and what-if 62 → 73
- re-normalisation (not zero) for missing indicators
- NaN for missing months
- EMI grace periods
- anomaly detection
- CSV validation
- what-if not persisting, progress persisting without changing the score
- the upload → reassess → comparison loop and idempotent re-upload
- onboarding with consent
- reset

## API (main endpoints)

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/businesses` | Portfolio with latest scores |
| POST | `/api/businesses` | Onboard a business (consent required) |
| GET | `/api/businesses/{id}/assessment` | Latest assessment: indicators, explanations, flags, plan |
| GET | `/api/businesses/{id}/assessments` | History |
| GET | `/api/businesses/{id}/comparison` | Latest vs previous |
| POST | `/api/businesses/{id}/assess` | Recalculate from stored records |
| POST | `/api/businesses/{id}/uploads/validate` | Validate a CSV without storing it |
| POST | `/api/businesses/{id}/uploads?skip_invalid=` | Store and reassess |
| GET | `/api/businesses/{id}/explanations` | Indicator explanations and flags |
| GET | `/api/businesses/{id}/recommendations` | Ranked plan with progress |
| POST | `/api/businesses/{id}/what-if` | Hypothetical score (not persisted) |
| PUT | `/api/businesses/{id}/progress/{action}` | Update progress (does not change the score) |
| GET | `/api/scoring/config` | Weights, thresholds, rules |
| GET | `/api/samples`, `/api/samples/{name}` | Sample CSVs |
| POST | `/api/demo/reset?confirm=true` | Restore demo data |

## What is functional, simulated, or out of scope

| Area | Status |
|---|---|
| Rules engine, CSV ingest/validation, flags, both dashboards, what-if, progress, reassessment, history, reset, light/dark themes | **Functional and tested** |
| What-if results | **Hypothetical**: indicators assumed to reach benchmark, never saved |
| Explanations | **Template-based** from the scoring output. The deck's LLM explanation layer is not included; no AI API is called |
| Data | **Synthetic** only |
| Merchant data separation | The owner view shows only the selected business. The "view as" switcher is a demo convenience; a real deployment needs authentication (not built) |
| Account Aggregator, GST, ULI feeds; ML scoring; lender workflows; approvals or rejections | **Future scope, not built** (AA appears only as a labelled placeholder) |

## Project layout

```
backend/
  app/scoring/      config (weights, thresholds), engine (metrics + compute_overall),
                    quality (flags), explain (templates), recommend (plan, what-if)
  app/services/     csv_ingest, assessment (persist/compare), seed, synthetic data
  app/api/routes.py thin FastAPI routes;  app/models.py ORM;  app/schemas.py
  data/samples/     sample CSVs;  db/schema_postgres.sql;  scripts/manage.py;  tests/
frontend/
  src/app/          overview, banker portfolio + assessment, merchant dashboard + records,
                    onboard, methodology
  src/components/   shell, theme, charts (Recharts), score table, upload flow
dist/               backup zips of frontend and backend source
```

## Deploying to Vercel

`vercel.json` at the repo root deploys both apps as one Vercel project with two services:

| Service | Root | Public path |
|---|---|---|
| `backend` (FastAPI, entrypoint `app/main.py`) | `backend/` | `/api/*` |
| `frontend` (Next.js) | `frontend/` | everything else |

The browser calls `/api/*` on the same domain, so no CORS setup or service bindings are needed. Locally, Next.js proxies `/api/*` to `BACKEND_URL`; on Vercel that proxy is switched off and the top-level rewrite does the routing. To run both services together locally the Vercel way, use `vercel dev`.

**Set `DATABASE_URL` (e.g. Supabase) in the Vercel project settings.** Without it, the backend falls back to SQLite in `/tmp`. That copy is reseeded on every cold start and is not shared between function instances, so uploads, progress and reassessments would not persist reliably. Uploads on Vercel are limited to 4 MB per file.

## Troubleshooting

- **"Cannot reach the CrediPath API"**: start the backend on port 8000, or set `BACKEND_URL` for the frontend.
- **Port in use**: run `uvicorn app.main:app --port 8001` and `BACKEND_URL=http://127.0.0.1:8001 npm run dev`.
- **Demo state looks odd**: run `python -m scripts.manage reset`, or delete `backend/data/credipath.db` and restart.
- **Fonts fail to download during `npm run build` offline**: the app falls back to system fonts in dev. Builds need internet access for Google Fonts.
