"""The CSV / record schema shared by ingestion, seeding and scoring."""

RECORD_TYPES = ["bank", "sale", "invoice", "supplier_payment", "loan_repayment"]

COLUMNS = [
    "record_type",
    "date",
    "amount",
    "direction",
    "counterparty",
    "category",
    "channel",
    "reference",
    "due_date",
    "paid_date",
    "balance_after",
    "notes",
]

# Columns every row must have, regardless of type.
BASE_REQUIRED = ["record_type", "date", "amount"]

# Extra fields that must be present for a row of that type to be usable.
REQUIRED_BY_TYPE: dict[str, list[str]] = {
    "bank": ["direction"],
    "sale": [],
    "invoice": ["counterparty", "due_date"],
    "supplier_payment": ["counterparty"],
    "loan_repayment": ["reference"],
}

# Fields that are not required, but whose absence lowers data completeness.
RECOMMENDED_BY_TYPE: dict[str, list[str]] = {
    "bank": ["counterparty", "category", "balance_after"],
    "sale": ["channel"],
    "invoice": ["reference"],
    "supplier_payment": ["due_date"],
    "loan_repayment": ["balance_after"],
}

DATE_FIELDS = ["date", "due_date", "paid_date"]
NUMERIC_FIELDS = ["amount", "balance_after"]
DIRECTIONS = {"credit", "debit"}

BANK_CATEGORIES = [
    "sales",
    "invoice_receipt",
    "loan_disbursal",
    "owner_capital",
    "internal_transfer",
    "refund",
    "supplier",
    "rent",
    "salary",
    "utilities",
    "loan_emi",
    "tax",
    "other",
]

FIELD_HELP = {
    "record_type": "One of: bank, sale, invoice, supplier_payment, loan_repayment",
    "date": "YYYY-MM-DD. Transaction date; invoice issue date; instalment due date for loan_repayment",
    "amount": "Positive number in rupees (no minus sign; use direction for bank rows)",
    "direction": "bank rows only: credit or debit",
    "counterparty": "Customer, supplier or payer name",
    "category": "bank rows: " + ", ".join(BANK_CATEGORIES),
    "channel": "UPI, NEFT, IMPS, cash, card, cheque",
    "reference": "Invoice number, loan account ID or UTR",
    "due_date": "YYYY-MM-DD. Required for invoices",
    "paid_date": "YYYY-MM-DD. Leave blank if not yet paid",
    "balance_after": "bank rows: account balance after the transaction; loan rows: outstanding principal",
    "notes": "Free text (ignored by scoring)",
}
