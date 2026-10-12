from datetime import date

import pytest

from app.services.csv_ingest import CSVFormatError, fingerprint, validate_csv

HEADER = "record_type,date,amount,direction,counterparty,category,channel,reference,due_date,paid_date,balance_after,notes\n"
TODAY = date(2026, 10, 12)


def v(body: str):
    return validate_csv((HEADER + body).encode(), today=TODAY)


def test_valid_rows_and_blank_stays_blank():
    r = v("bank,2026-08-07,\"31,250\",CR,PhonePe,sales,UPI,,,,,\n")
    assert r["error_count"] == 0
    row = r["rows"][0]
    assert row["amount"] == 31250 and row["direction"] == "credit"
    assert row["balance_after"] is None  # not filled with zero
    assert any("balance_after" in w["message"] for w in r["warnings"])


def test_date_formats():
    r = v("sale,07/08/2026,1000,,,,UPI,,,,,\nsale,2026-08-08,1000,,,,UPI,,,,,\n")
    assert [x["date"] for x in r["rows"]] == [date(2026, 8, 7), date(2026, 8, 8)]


def test_future_date_rejected():
    r = v("sale,2027-01-01,1000,,,,UPI,,,,,\n")
    assert r["error_count"] == 1 and "future" in r["errors"][0]["message"]


def test_type_specific_requirements():
    r = v("invoice,2026-08-01,1000,,Cafe,,,INV1,,,,\nloan_repayment,2026-08-05,1000,,Bank,,,,,,,\n")
    fields = sorted(e["field"] for e in r["errors"])
    assert fields == ["due_date", "reference"]


def test_empty_and_header_only():
    with pytest.raises(CSVFormatError):
        validate_csv(b"")
    with pytest.raises(CSVFormatError):
        validate_csv(HEADER.encode())


def test_unknown_category_warns_and_maps_to_other():
    r = v("bank,2026-08-07,100,debit,X,snacks,UPI,,,,10,\n")
    assert r["rows"][0]["category"] == "other"
    assert any("Unrecognised category" in w["message"] for w in r["warnings"])


def test_invoice_fingerprint_is_reference_based():
    a = {"record_type": "invoice", "reference": "INV-1", "date": date(2026, 1, 1), "amount": 10.0}
    b = dict(a, amount=20.0, paid_date=date(2026, 2, 1))
    assert fingerprint(a) == fingerprint(b)
    c = {"record_type": "bank", "date": date(2026, 1, 1), "amount": 10.0, "direction": "credit", "_occurrence": 1}
    assert fingerprint(c) != fingerprint(dict(c, _occurrence=2))
