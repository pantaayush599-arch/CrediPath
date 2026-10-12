from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app

SAMPLES = Path(__file__).resolve().parent.parent / "data" / "samples"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        c.headers["Authorization"] = "Bearer " + _token(c, "officer@demobank.in", "Banker@123")
        r = c.post("/api/demo/reset?confirm=true")
        assert r.status_code == 200
        c.headers["Authorization"] = "Bearer " + _token(c, "officer@demobank.in", "Banker@123")
        yield c


def _token(c, email, password, role=None):
    r = c.post("/api/auth/login", json={"email": email, "password": password, "role": role})
    assert r.status_code == 200, r.text
    return r.json()["token"]


def _upload(client, biz, name, **params):
    with open(SAMPLES / name, "rb") as f:
        return client.post(f"/api/businesses/{biz}/uploads", files={"file": (name, f, "text/csv")}, params=params)


def test_seeded_portfolio(client):
    rows = client.get("/api/businesses").json()
    ids = [b["id"] for b in rows]
    assert ids[0] == "rajs-bakery" and len(ids) == 4
    raj = rows[0]
    assert raj["latest_score"] == 61.75 and raj["latest_display_score"] == 62
    assert raj["is_synthetic"] is True


def test_both_views_share_one_assessment(client):
    a = client.get("/api/businesses/rajs-bakery/assessment").json()
    recs = client.get("/api/businesses/rajs-bakery/recommendations").json()
    expl = client.get("/api/businesses/rajs-bakery/explanations").json()
    assert recs["assessment_id"] == a["id"] == expl["assessment_id"]
    assert sum(i["contribution"] for i in a["indicators"]) == pytest.approx(a["overall_score"])
    assert any(f["kind"] == "overdue_receivables" and f["requires_verification"] for f in a["flags"])
    assert a["summary"]["strengths"] == ["revenue_consistency", "repayment_record"]


def test_what_if_is_not_persisted(client):
    before = client.get("/api/businesses/rajs-bakery/assessments").json()
    r = client.post("/api/businesses/rajs-bakery/what-if", json={"actions": ["collect_overdue_invoices", "complete_records", "stabilise_cash_flow", "build_cash_buffer"]})
    assert r.status_code == 200
    body = r.json()
    assert body["baseline_display"] == 62 and body["hypothetical_display"] == 73
    after = client.get("/api/businesses/rajs-bakery/assessments").json()
    assert len(after) == len(before)


def test_progress_persists_and_does_not_change_score(client):
    r = client.put("/api/businesses/rajs-bakery/progress/collect_overdue_invoices", json={"status": "completed"})
    assert r.status_code == 200
    a = client.get("/api/businesses/rajs-bakery/assessment").json()
    assert a["overall_score"] == 61.75
    status = {x["action_key"]: x["status"] for x in a["recommendations"]}
    assert status["collect_overdue_invoices"] == "completed"
    assert client.put("/api/businesses/rajs-bakery/progress/nope", json={"status": "completed"}).status_code == 404
    assert client.put("/api/businesses/rajs-bakery/progress/complete_records", json={"status": "done"}).status_code == 422


def test_invalid_csv_rejected_without_storing(client):
    n_before = client.get("/api/businesses/rajs-bakery").json()["record_stats"]
    r = _upload(client, "rajs-bakery", "invalid_example.csv")
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert detail["validation"]["error_count"] == 8
    assert client.get("/api/businesses/rajs-bakery").json()["record_stats"] == n_before


def test_bad_header_and_wrong_type(client):
    r = client.post("/api/businesses/rajs-bakery/uploads/validate", files={"file": ("x.csv", b"foo,bar\n1,2\n", "text/csv")})
    assert r.status_code == 422 and "Missing required column" in r.json()["detail"]
    r = client.post("/api/businesses/rajs-bakery/uploads/validate", files={"file": ("x.txt", b"a", "text/plain")})
    assert r.status_code == 415


def test_reassessment_loop(client):
    r = _upload(client, "rajs-bakery", "raj_bakery_update_sep2026.csv")
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["rows_updated"] == 5  # five invoices now collected
    cmp = body["comparison"]
    assert cmp["previous"]["overall_score"] == 61.75
    assert cmp["current"]["overall_score"] > 61.75
    inv = next(i for i in cmp["indicators"] if i["key"] == "invoice_collection")
    assert inv["after"] > inv["before"]
    assert any("overdue receivable" in t for t in cmp["flags_resolved"])
    # Banker view now shows the updated profile.
    assert client.get("/api/businesses/rajs-bakery").json()["latest_score"] == cmp["current"]["overall_score"]
    assert client.get("/api/businesses/rajs-bakery/comparison").json()["score_delta"] == cmp["score_delta"]
    # Re-uploading the same file changes nothing.
    again = _upload(client, "rajs-bakery", "raj_bakery_update_sep2026.csv").json()
    assert again["rows_inserted"] == 0 and again["assessment"] is None


def test_onboard_new_business(client):
    body = {"name": "Fresh Fruits Co", "owner_name": "Test Owner", "category": "Fruit retail", "city": "Pune", "email": "asha@freshfruits.in", "password": "Fruit@123"}
    r = client.post("/api/businesses", json={**body, "consent": False})
    assert r.status_code == 422
    r = client.post("/api/businesses", json={**body, "consent": True})
    assert r.status_code == 201
    biz = r.json()["business"]["id"]
    owner = {"Authorization": "Bearer " + r.json()["token"]}
    assert client.post("/api/businesses", json={**body, "consent": True}).status_code == 409
    assert client.get(f"/api/businesses/{biz}/assessment", headers=owner).status_code == 404
    with open(SAMPLES / "new_business_sample.csv", "rb") as f:
        up = client.post(f"/api/businesses/{biz}/uploads", files={"file": ("s.csv", f, "text/csv")}, headers=owner)
    assert up.status_code == 201
    assert up.json()["assessment"]["overall_score"] is not None
    assert up.json()["comparison"] is None
    # The new owner can sign in and sees only their business.
    assert client.get("/api/businesses/rajs-bakery", headers=owner).status_code == 403


def test_login_and_access_control(client):
    assert client.post("/api/auth/login", json={"email": "raj@rajsbakery.in", "password": "nope"}).status_code == 401
    assert client.post("/api/auth/login", json={"email": "raj@rajsbakery.in", "password": "Raj@123", "role": "banker"}).status_code == 403
    raj = {"Authorization": "Bearer " + _token(client, "raj@rajsbakery.in", "Raj@123", "merchant")}
    assert client.get("/api/auth/me", headers=raj).json()["business_id"] == "rajs-bakery"
    assert client.get("/api/businesses/rajs-bakery/assessment", headers=raj).status_code == 200
    assert client.get("/api/businesses/meena-general-store/assessment", headers=raj).status_code == 403
    assert client.get("/api/businesses", headers=raj).status_code == 403
    assert client.post("/api/demo/reset?confirm=true", headers=raj).status_code == 403
    assert client.get("/api/businesses/rajs-bakery", headers={"Authorization": "Bearer junk"}).status_code == 401
    assert client.get("/api/businesses/rajs-bakery", headers={"Authorization": ""}).status_code == 401
    accounts = client.get("/api/auth/demo-accounts", headers={"Authorization": ""}).json()
    assert {a["role"] for a in accounts} == {"banker", "merchant"}


def test_reset_restores_original_state(client):
    assert client.post("/api/demo/reset").status_code == 400
    r = client.post("/api/demo/reset?confirm=true")
    assert r.status_code == 200
    # The banker account is re-created by the reset, so the same token still works.
    rows = client.get("/api/businesses").json()
    assert [b["id"] for b in rows] == ["rajs-bakery", "meena-general-store", "sharma-mobile-electronics", "green-leaf-tiffin"]
    assert rows[0]["latest_score"] == 61.75 and rows[0]["assessment_count"] == 1
    assert client.get("/api/businesses/rajs-bakery/progress").json() == []
    hist = client.get("/api/businesses/meena-general-store/assessments").json()
    assert len(hist) == 3


def test_samples_downloadable(client):
    names = [s["name"] for s in client.get("/api/samples", headers={"Authorization": ""}).json()]
    assert "raj_bakery_update_sep2026.csv" in names
    r = client.get("/api/samples/credipath_template.csv")
    assert r.status_code == 200 and r.text.startswith("record_type,date,amount")
    assert client.get("/api/samples/..%2Fcredipath.db").status_code == 404
