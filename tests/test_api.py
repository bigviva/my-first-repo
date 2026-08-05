"""End-to-end API tests for the main workflows."""
import io
import os

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setenv("CAT_DB_PATH", db_path)
    # database module reads DB_PATH at import; patch the module attribute too
    from app import database
    monkeypatch.setattr(database, "DB_PATH", db_path)
    database.init_db(db_path)
    from app.main import app
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def user(client):
    return client.post("/api/users", json={
        "name": "Test Owner", "email": "owner@example.com", "department": "Quality"}).json()


def test_escape_lifecycle_with_rating_and_escalation(client, user):
    r = client.post("/api/escapes", json={
        "title": "Cracked part shipped", "escape_type": "external", "customer": "ACME",
        "severity": 4, "likelihood": 3, "owner_id": user["id"]})
    assert r.status_code == 201
    esc = r.json()
    assert esc["ref"] == "ESC-0001"
    assert esc["rating_score"] == 12
    assert esc["escalation_level"] == "Executive"

    # high-rated escape generated an escalation notification
    detail = client.get(f"/api/escapes/{esc['id']}").json()
    assert any("Executive" in n["message"] for n in detail["notifications"])

    # invalid transition rejected
    bad = client.post(f"/api/escapes/{esc['id']}/status", json={"status": "Pending Closure"})
    assert bad.status_code == 400

    # closure blocked without containment plan
    blocked = client.post(f"/api/escapes/{esc['id']}/status", json={"status": "Closed"})
    assert blocked.status_code == 400
    assert "containment" in blocked.json()["detail"]

    client.patch(f"/api/escapes/{esc['id']}", json={"containment_plan": "Lot quarantined"})
    ok = client.post(f"/api/escapes/{esc['id']}/status", json={"status": "Closed"})
    assert ok.status_code == 200
    assert ok.json()["status"] == "Closed"
    assert ok.json()["closed_at"]


def test_rating_recomputed_on_update(client):
    esc = client.post("/api/escapes", json={
        "title": "Minor issue", "severity": 1, "likelihood": 1}).json()
    assert esc["escalation_level"] == "None"
    updated = client.patch(f"/api/escapes/{esc['id']}",
                           json={"severity": 4, "likelihood": 4}).json()
    assert updated["rating_score"] == 16
    assert updated["escalation_level"] == "Executive"


def test_car_full_workflow(client, user):
    car = client.post("/api/cars", json={
        "title": "Supplier weld porosity", "car_type": "external",
        "supplier": "WeldCo", "owner_id": user["id"]}).json()
    assert car["status"] == "Draft"

    # cannot issue an unvalidated CAR
    assert client.post(f"/api/cars/{car['id']}/issue").status_code == 400

    # validation rejection keeps it in draft
    rej = client.post(f"/api/cars/{car['id']}/validate",
                      json={"approved": False, "validation_notes": "duplicate check missing"})
    assert rej.json()["status"] == "Draft"

    ok = client.post(f"/api/cars/{car['id']}/validate",
                     json={"approved": True, "validated_by": user["id"],
                           "validation_notes": "scope confirmed"})
    assert ok.json()["status"] == "Validated"

    issued = client.post(f"/api/cars/{car['id']}/issue").json()
    assert issued["status"] == "Issued"

    resp = client.post(f"/api/cars/{car['id']}/respond",
                       json={"response_text": "Adjusted weld parameters, retrained operators."})
    assert resp.json()["status"] == "Response Submitted"

    rejected = client.post(f"/api/cars/{car['id']}/decision",
                           json={"accept": False, "notes": "no objective evidence"})
    assert rejected.json()["status"] == "Response Rejected"

    resub = client.post(f"/api/cars/{car['id']}/respond",
                        json={"response_text": "Added X-ray inspection data for 3 lots."})
    assert resub.json()["status"] == "Response Submitted"

    accepted = client.post(f"/api/cars/{car['id']}/decision", json={"accept": True})
    assert accepted.json()["status"] == "Response Accepted"

    closed = client.post(f"/api/cars/{car['id']}/close").json()
    assert closed["status"] == "Closed"
    assert closed["closed_at"]

    history = client.get(f"/api/cars/{car['id']}").json()["history"]
    actions = [h["action"] for h in history]
    for expected in ("created", "validated", "issued", "response-submitted",
                     "response-rejected", "response-accepted", "closed"):
        assert expected in actions


def test_car_response_recommendations(client):
    # historical CAR with an accepted response
    old = client.post("/api/cars", json={
        "title": "Weld porosity on frame assembly", "car_type": "external",
        "description": "Porosity found in supplier welds"}).json()
    client.post(f"/api/cars/{old['id']}/validate", json={"approved": True})
    client.post(f"/api/cars/{old['id']}/issue")
    client.post(f"/api/cars/{old['id']}/respond",
                json={"response_text": "Requalified weld schedule and added NDT sampling."})
    client.post(f"/api/cars/{old['id']}/decision", json={"accept": True})

    new = client.post("/api/cars", json={
        "title": "Weld porosity on bracket", "car_type": "external",
        "description": "Porosity in welds from new supplier"}).json()
    recs = client.get(f"/api/cars/{new['id']}/response-recommendations").json()
    assert recs
    assert recs[0]["car_ref"] == old["ref"]
    assert "weld" in recs[0]["response_text"].lower() or recs[0]["score"] > 0


def test_capa_lifecycle_and_effectiveness(client, user):
    capa = client.post("/api/capas", json={
        "title": "Fix training gap", "rcca_method": "5-Why",
        "root_cause_category": "Training", "owner_id": user["id"]}).json()
    assert capa["status"] == "Open"

    client.post(f"/api/capas/{capa['id']}/status", json={"status": "RCCA In Progress"})
    client.patch(f"/api/capas/{capa['id']}", json={
        "root_cause": "Onboarding skips torque certification",
        "corrective_action": "Certify all current operators",
        "preventive_action": "Add certification to onboarding checklist"})
    client.post(f"/api/capas/{capa['id']}/status", json={"status": "Actions In Progress"})
    r = client.post(f"/api/capas/{capa['id']}/status", json={"status": "Effectiveness Verification"})
    assert r.status_code == 200

    # closure only via verification, not direct status change
    direct = client.post(f"/api/capas/{capa['id']}/status", json={"status": "Closed"})
    assert direct.status_code == 400

    # not-effective sends it back to rework
    back = client.post(f"/api/capas/{capa['id']}/verify", json={
        "effective": False, "effectiveness_result": "recurrence seen", "verified_by": user["id"]})
    assert back.json()["status"] == "Actions In Progress"
    assert back.json()["effective"] == 0

    client.post(f"/api/capas/{capa['id']}/status", json={"status": "Effectiveness Verification"})
    done = client.post(f"/api/capas/{capa['id']}/verify", json={
        "effective": True, "effectiveness_result": "no recurrence in 90 days",
        "verified_by": user["id"]})
    assert done.json()["status"] == "Closed"
    assert done.json()["effective"] == 1
    assert done.json()["closed_at"]


def test_capa_requires_root_cause_before_verification(client):
    capa = client.post("/api/capas", json={"title": "No RCCA yet"}).json()
    client.post(f"/api/capas/{capa['id']}/status", json={"status": "RCCA In Progress"})
    client.post(f"/api/capas/{capa['id']}/status", json={"status": "Actions In Progress"})
    r = client.post(f"/api/capas/{capa['id']}/status", json={"status": "Effectiveness Verification"})
    assert r.status_code == 400
    assert "root cause" in r.json()["detail"]


def test_capa_assignment_suggestions(client):
    u1 = client.post("/api/users", json={
        "name": "Veteran", "email": "vet@example.com", "department": "Quality"}).json()
    u2 = client.post("/api/users", json={
        "name": "Newbie", "email": "new@example.com", "department": "Quality"}).json()
    # give u1 an effective closed CAPA in Training
    capa = client.post("/api/capas", json={
        "title": "Old training fix", "root_cause_category": "Training",
        "owner_id": u1["id"]}).json()
    client.post(f"/api/capas/{capa['id']}/status", json={"status": "RCCA In Progress"})
    client.patch(f"/api/capas/{capa['id']}", json={"root_cause": "gap"})
    client.post(f"/api/capas/{capa['id']}/status", json={"status": "Actions In Progress"})
    client.post(f"/api/capas/{capa['id']}/status", json={"status": "Effectiveness Verification"})
    client.post(f"/api/capas/{capa['id']}/verify", json={"effective": True})

    sugs = client.get("/api/capas/assignment-suggestions?root_cause_category=Training").json()
    assert sugs[0]["user_id"] == u1["id"]
    assert sugs[0]["effective_capas_closed"] == 1


def test_bulletin_creation_notifies_audience(client, user):
    car = client.post("/api/cars", json={"title": "Alert source CAR"}).json()
    b = client.post("/api/bulletins", json={
        "title": "Check torque specs", "body": "Verify revision before use.",
        "car_id": car["id"], "audience": "Line 3", "issued_by": user["id"]})
    assert b.status_code == 201
    assert b.json()["ref"] == "QAB-0001"
    car_detail = client.get(f"/api/cars/{car['id']}").json()
    assert len(car_detail["bulletins"]) == 1


def test_overdue_escalation_sweep(client, user):
    esc = client.post("/api/escapes", json={
        "title": "Old overdue escape", "due_date": "2020-01-01", "owner_id": user["id"]}).json()
    assert esc["escalation_level"] == "Level 1"  # 3*2 = 6
    r = client.post("/api/run-escalation").json()
    assert r["count"] == 1
    assert r["escalated"][0]["new_level"] == "Level 2"
    detail = client.get(f"/api/escapes/{esc['id']}").json()
    assert detail["escalation_level"] == "Level 2"
    assert any("overdue" in n["message"] for n in detail["notifications"])


def test_csv_import(client):
    csv_data = (
        "title,escape_type,customer,severity,likelihood,status\n"
        "Imported escape one,external,ACME,4,2,Open\n"
        "Imported escape two,internal,,2,1,Closed\n"
        ",internal,,1,1,Open\n"  # missing title -> error
    )
    r = client.post("/api/import/escapes",
                    files={"file": ("legacy.csv", io.BytesIO(csv_data.encode()), "text/csv")})
    assert r.status_code == 200
    body = r.json()
    assert body["imported"] == 2
    assert len(body["errors"]) == 1
    escapes = client.get("/api/escapes").json()
    assert len(escapes) == 2
    imported = next(e for e in escapes if e["title"] == "Imported escape one")
    assert imported["rating_score"] == 8
    assert imported["escalation_level"] == "Level 2"


def test_dashboard(client, user):
    client.post("/api/escapes", json={"title": "One", "severity": 4, "likelihood": 4})
    client.post("/api/cars", json={"title": "Two"})
    d = client.get("/api/dashboard").json()
    assert d["escapes"]["total"] == 1
    assert d["escapes"]["escalated"] == 1
    assert d["cars"]["open"] == 1
    assert d["recent_history"]
