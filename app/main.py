"""Corrective Actions Tracking System — FastAPI application.

Covers the Concern Module scope:
- Processing of Escapes (internal/external repository, common rating and
  escalation, containment plans, notifications, tracking to closure)
- Processing of CARs (validation prior to issuance, internal/external CARs,
  supplier response submission with accept/reject, escalation and tracking
  to closure, response recommendations, quality alert bulletins)
- Processing of CAPA (RCCA capture, historically-effective RCCA assist,
  effectiveness verification, assignment suggestions, tracking to closure)
"""
import csv
import io
import os
import sqlite3
from contextlib import asynccontextmanager
from datetime import date
from typing import Optional

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import analytics
from . import database as db
from . import models as m
from . import rating, recommendations

STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "static")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    db.init_db()
    yield


app = FastAPI(title="Corrective Actions Tracking System", version="1.0.0", lifespan=lifespan)


def _row(row: Optional[sqlite3.Row]) -> dict:
    return dict(row) if row is not None else {}


def _rows(rows) -> list[dict]:
    return [dict(r) for r in rows]


def _get_or_404(conn, table: str, record_id: int) -> sqlite3.Row:
    row = conn.execute(f"SELECT * FROM {table} WHERE id = ?", (record_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"{table[:-1]} {record_id} not found")
    return row


def _owner_name(conn, owner_id) -> str:
    if owner_id is None:
        return ""
    row = conn.execute("SELECT name FROM users WHERE id = ?", (owner_id,)).fetchone()
    return row["name"] if row else ""


def _is_overdue(record: dict) -> bool:
    due = record.get("due_date")
    return bool(due) and record.get("status") != "Closed" and due < date.today().isoformat()


def _with_meta(conn, record: dict) -> dict:
    record["owner_name"] = _owner_name(conn, record.get("owner_id"))
    record["overdue"] = _is_overdue(record)
    return record


# ---------------------------------------------------------------- dashboard

@app.get("/api/dashboard")
def dashboard() -> dict:
    with db.get_conn() as conn:
        out: dict = {}
        for table, key in (("escapes", "escapes"), ("cars", "cars"), ("capas", "capas")):
            rows = _rows(conn.execute(f"SELECT * FROM {table}"))
            open_rows = [r for r in rows if r["status"] != "Closed"]
            out[key] = {
                "total": len(rows),
                "open": len(open_rows),
                "closed": len(rows) - len(open_rows),
                "overdue": sum(1 for r in open_rows if _is_overdue(r)),
                "by_status": {},
            }
            for r in rows:
                out[key]["by_status"][r["status"]] = out[key]["by_status"].get(r["status"], 0) + 1
        out["escapes"]["escalated"] = conn.execute(
            "SELECT COUNT(*) AS n FROM escapes WHERE escalation_level != 'None' AND status != 'Closed'"
        ).fetchone()["n"]
        out["capas"]["effective_rate"] = None
        verified = _rows(conn.execute("SELECT effective FROM capas WHERE effective IS NOT NULL"))
        if verified:
            out["capas"]["effective_rate"] = round(
                100 * sum(1 for v in verified if v["effective"]) / len(verified))
        out["bulletins"] = conn.execute("SELECT COUNT(*) AS n FROM bulletins").fetchone()["n"]
        out["recent_history"] = _rows(conn.execute(
            "SELECT * FROM history ORDER BY id DESC LIMIT 12"))
        return out


@app.get("/api/analytics")
def get_analytics() -> dict:
    with db.get_conn() as conn:
        return analytics.compute(conn)


# -------------------------------------------------------------------- users

@app.get("/api/users")
def list_users() -> list[dict]:
    with db.get_conn() as conn:
        return _rows(conn.execute("SELECT * FROM users ORDER BY name"))


@app.post("/api/users", status_code=201)
def create_user(body: m.UserIn) -> dict:
    with db.get_conn() as conn:
        try:
            cur = conn.execute(
                "INSERT INTO users (name, email, department) VALUES (?, ?, ?)",
                (body.name, body.email, body.department))
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=409, detail="email already exists")
        return _row(conn.execute("SELECT * FROM users WHERE id = ?", (cur.lastrowid,)).fetchone())


# ------------------------------------------------------------------ escapes

ESCAPE_TRANSITIONS = {
    "Open": {"Containment", "In Progress", "Closed"},
    "Containment": {"In Progress"},
    "In Progress": {"Pending Closure"},
    "Pending Closure": {"Closed", "In Progress"},
    "Closed": {"In Progress"},  # reopen
}


@app.get("/api/escapes")
def list_escapes(status: str = "", escape_type: str = "", q: str = "") -> list[dict]:
    with db.get_conn() as conn:
        sql = "SELECT * FROM escapes WHERE 1=1"
        params: list = []
        if status:
            sql += " AND status = ?"
            params.append(status)
        if escape_type:
            sql += " AND escape_type = ?"
            params.append(escape_type)
        if q:
            sql += " AND (title LIKE ? OR description LIKE ? OR ref LIKE ? OR customer LIKE ? OR part_number LIKE ?)"
            params.extend([f"%{q}%"] * 5)
        sql += " ORDER BY id DESC"
        return [_with_meta(conn, r) for r in _rows(conn.execute(sql, params))]


@app.get("/api/escapes/{escape_id}")
def get_escape(escape_id: int) -> dict:
    with db.get_conn() as conn:
        rec = _with_meta(conn, _row(_get_or_404(conn, "escapes", escape_id)))
        rec["severity_label"] = rating.SEVERITY_LABELS[rec["severity"]]
        rec["likelihood_label"] = rating.LIKELIHOOD_LABELS[rec["likelihood"]]
        rec["linked_cars"] = _rows(conn.execute(
            "SELECT id, ref, title, status FROM cars WHERE escape_id = ?", (escape_id,)))
        rec["history"] = _rows(conn.execute(
            "SELECT * FROM history WHERE record_type='escape' AND record_id=? ORDER BY id DESC",
            (escape_id,)))
        rec["notifications"] = _rows(conn.execute(
            "SELECT * FROM notifications WHERE record_type='escape' AND record_id=? ORDER BY id DESC",
            (escape_id,)))
        return rec


@app.post("/api/escapes", status_code=201)
def create_escape(body: m.EscapeIn) -> dict:
    with db.get_conn() as conn:
        score, level = rating.rate(body.severity, body.likelihood)
        ref = db.next_ref(conn, "escapes", "ESC")
        cur = conn.execute(
            """INSERT INTO escapes (ref, title, description, escape_type, customer, program,
                   part_number, severity, likelihood, rating_score, escalation_level,
                   containment_plan, containment_due, due_date, owner_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (ref, body.title, body.description, body.escape_type, body.customer, body.program,
             body.part_number, body.severity, body.likelihood, score, level,
             body.containment_plan, body.containment_due, body.due_date, body.owner_id))
        db.log_history(conn, "escape", cur.lastrowid, "created", f"{ref}: {body.title}")
        if level != "None":
            db.send_notification(conn, "escape", cur.lastrowid, "quality-management",
                                 f"{ref} rated {score} ({level} escalation): {body.title}")
        return _with_meta(conn, _row(conn.execute(
            "SELECT * FROM escapes WHERE id = ?", (cur.lastrowid,)).fetchone()))


@app.patch("/api/escapes/{escape_id}")
def update_escape(escape_id: int, body: m.EscapeUpdate) -> dict:
    with db.get_conn() as conn:
        rec = _row(_get_or_404(conn, "escapes", escape_id))
        changes = {k: v for k, v in body.model_dump().items() if v is not None}
        if not changes:
            return _with_meta(conn, rec)
        merged = {**rec, **changes}
        score, level = rating.rate(merged["severity"], merged["likelihood"])
        changes["rating_score"], changes["escalation_level"] = score, level
        sets = ", ".join(f"{k} = ?" for k in changes) + ", updated_at = datetime('now')"
        conn.execute(f"UPDATE escapes SET {sets} WHERE id = ?", (*changes.values(), escape_id))
        db.log_history(conn, "escape", escape_id, "updated",
                       ", ".join(k for k in changes if k not in ("rating_score", "escalation_level")))
        if level != rec["escalation_level"]:
            db.send_notification(conn, "escape", escape_id, "quality-management",
                                 f"{rec['ref']} escalation changed to {level} (score {score})")
        return _with_meta(conn, _row(conn.execute(
            "SELECT * FROM escapes WHERE id = ?", (escape_id,)).fetchone()))


@app.post("/api/escapes/{escape_id}/status")
def escape_status(escape_id: int, body: m.StatusChange) -> dict:
    with db.get_conn() as conn:
        rec = _row(_get_or_404(conn, "escapes", escape_id))
        allowed = ESCAPE_TRANSITIONS.get(rec["status"], set())
        if body.status not in allowed:
            raise HTTPException(
                status_code=400,
                detail=f"cannot move escape from '{rec['status']}' to '{body.status}' (allowed: {sorted(allowed)})")
        if body.status == "Closed" and not rec["containment_plan"]:
            raise HTTPException(status_code=400, detail="containment plan required before closure")
        closed_at = "datetime('now')" if body.status == "Closed" else "NULL"
        conn.execute(
            f"UPDATE escapes SET status = ?, closed_at = {closed_at}, updated_at = datetime('now') WHERE id = ?",
            (body.status, escape_id))
        db.log_history(conn, "escape", escape_id, "status",
                       f"{rec['status']} -> {body.status}" + (f" ({body.note})" if body.note else ""),
                       body.changed_by)
        return _with_meta(conn, _row(conn.execute(
            "SELECT * FROM escapes WHERE id = ?", (escape_id,)).fetchone()))


@app.post("/api/escapes/{escape_id}/notify", status_code=201)
def escape_notify(escape_id: int, body: m.NotificationIn) -> dict:
    with db.get_conn() as conn:
        rec = _row(_get_or_404(conn, "escapes", escape_id))
        db.send_notification(conn, "escape", escape_id, body.recipient, body.message)
        db.log_history(conn, "escape", escape_id, "notified", f"to {body.recipient}")
        return {"ok": True, "ref": rec["ref"]}


# --------------------------------------------------------------------- cars

@app.get("/api/cars")
def list_cars(status: str = "", car_type: str = "", q: str = "") -> list[dict]:
    with db.get_conn() as conn:
        sql = "SELECT * FROM cars WHERE 1=1"
        params: list = []
        if status:
            sql += " AND status = ?"
            params.append(status)
        if car_type:
            sql += " AND car_type = ?"
            params.append(car_type)
        if q:
            sql += " AND (title LIKE ? OR description LIKE ? OR ref LIKE ? OR supplier LIKE ?)"
            params.extend([f"%{q}%"] * 4)
        sql += " ORDER BY id DESC"
        return [_with_meta(conn, r) for r in _rows(conn.execute(sql, params))]


@app.get("/api/cars/{car_id}")
def get_car(car_id: int) -> dict:
    with db.get_conn() as conn:
        rec = _with_meta(conn, _row(_get_or_404(conn, "cars", car_id)))
        if rec["escape_id"]:
            esc = conn.execute("SELECT ref, title FROM escapes WHERE id = ?", (rec["escape_id"],)).fetchone()
            rec["escape_ref"] = esc["ref"] if esc else None
        rec["linked_capas"] = _rows(conn.execute(
            "SELECT id, ref, title, status FROM capas WHERE car_id = ?", (car_id,)))
        rec["bulletins"] = _rows(conn.execute(
            "SELECT id, ref, title, audience, issued_at FROM bulletins WHERE car_id = ?", (car_id,)))
        rec["history"] = _rows(conn.execute(
            "SELECT * FROM history WHERE record_type='car' AND record_id=? ORDER BY id DESC", (car_id,)))
        return rec


@app.post("/api/cars", status_code=201)
def create_car(body: m.CarIn) -> dict:
    with db.get_conn() as conn:
        if body.escape_id is not None:
            _get_or_404(conn, "escapes", body.escape_id)
        ref = db.next_ref(conn, "cars", "CAR")
        cur = conn.execute(
            """INSERT INTO cars (ref, title, description, car_type, supplier, escape_id,
                   severity, due_date, owner_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (ref, body.title, body.description, body.car_type, body.supplier, body.escape_id,
             body.severity, body.due_date, body.owner_id))
        db.log_history(conn, "car", cur.lastrowid, "created", f"{ref}: {body.title} (draft)")
        return _with_meta(conn, _row(conn.execute(
            "SELECT * FROM cars WHERE id = ?", (cur.lastrowid,)).fetchone()))


@app.patch("/api/cars/{car_id}")
def update_car(car_id: int, body: m.CarUpdate) -> dict:
    with db.get_conn() as conn:
        rec = _row(_get_or_404(conn, "cars", car_id))
        changes = {k: v for k, v in body.model_dump().items() if v is not None}
        if changes:
            sets = ", ".join(f"{k} = ?" for k in changes) + ", updated_at = datetime('now')"
            conn.execute(f"UPDATE cars SET {sets} WHERE id = ?", (*changes.values(), car_id))
            db.log_history(conn, "car", car_id, "updated", ", ".join(changes))
        return _with_meta(conn, _row(conn.execute(
            "SELECT * FROM cars WHERE id = ?", (car_id,)).fetchone()))


def _car_transition(conn, car_id: int, from_statuses: set[str], to_status: str,
                    action: str, detail: str, extra_sql: str = "", extra_params: tuple = ()):
    rec = _row(_get_or_404(conn, "cars", car_id))
    if rec["status"] not in from_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"CAR must be in {sorted(from_statuses)} (currently '{rec['status']}')")
    conn.execute(
        f"UPDATE cars SET status = ?{extra_sql}, updated_at = datetime('now') WHERE id = ?",
        (to_status, *extra_params, car_id))
    db.log_history(conn, "car", car_id, action, detail)
    return _row(conn.execute("SELECT * FROM cars WHERE id = ?", (car_id,)).fetchone())


@app.post("/api/cars/{car_id}/validate")
def validate_car(car_id: int, body: m.CarValidation) -> dict:
    """Validation of the CAR prior to issuance."""
    with db.get_conn() as conn:
        if not body.approved:
            rec = _row(_get_or_404(conn, "cars", car_id))
            db.log_history(conn, "car", car_id, "validation-rejected", body.validation_notes)
            return _with_meta(conn, rec)
        rec = _car_transition(
            conn, car_id, {"Draft"}, "Validated", "validated", body.validation_notes,
            ", validated_by = ?, validated_at = datetime('now'), validation_notes = ?",
            (body.validated_by, body.validation_notes))
        return _with_meta(conn, rec)


@app.post("/api/cars/{car_id}/issue")
def issue_car(car_id: int) -> dict:
    with db.get_conn() as conn:
        rec = _car_transition(conn, car_id, {"Validated"}, "Issued", "issued", "CAR issued")
        recipient = rec["supplier"] or "responsible-party"
        db.send_notification(conn, "car", car_id, recipient,
                             f"{rec['ref']} issued: {rec['title']}. Response due {rec['due_date'] or 'TBD'}.")
        return _with_meta(conn, rec)


@app.post("/api/cars/{car_id}/respond")
def submit_car_response(car_id: int, body: m.CarResponse) -> dict:
    with db.get_conn() as conn:
        rec = _car_transition(
            conn, car_id, {"Issued", "Response Rejected"}, "Response Submitted",
            "response-submitted", body.response_text[:120],
            ", response_text = ?, response_submitted_at = datetime('now')",
            (body.response_text,))
        return _with_meta(conn, rec)


@app.post("/api/cars/{car_id}/decision")
def decide_car_response(car_id: int, body: m.CarDecision) -> dict:
    """Accept or reject the submitted response."""
    with db.get_conn() as conn:
        to_status = "Response Accepted" if body.accept else "Response Rejected"
        rec = _car_transition(
            conn, car_id, {"Response Submitted"}, to_status,
            "response-accepted" if body.accept else "response-rejected", body.notes,
            ", response_decision_notes = ?", (body.notes,))
        if not body.accept:
            recipient = rec["supplier"] or "responsible-party"
            db.send_notification(conn, "car", car_id, recipient,
                                 f"{rec['ref']} response rejected: {body.notes or 'see notes'}")
        return _with_meta(conn, rec)


@app.post("/api/cars/{car_id}/close")
def close_car(car_id: int) -> dict:
    with db.get_conn() as conn:
        rec = _car_transition(
            conn, car_id, {"Response Accepted"}, "Closed", "closed", "CAR closed",
            ", closed_at = datetime('now')")
        return _with_meta(conn, rec)


@app.get("/api/cars/{car_id}/response-recommendations")
def car_response_recs(car_id: int) -> list[dict]:
    with db.get_conn() as conn:
        _get_or_404(conn, "cars", car_id)
        return recommendations.car_response_recommendations(conn, car_id)


# -------------------------------------------------------------------- capas

CAPA_TRANSITIONS = {
    "Open": {"RCCA In Progress"},
    "RCCA In Progress": {"Actions In Progress"},
    "Actions In Progress": {"Effectiveness Verification"},
    "Effectiveness Verification": {"Actions In Progress"},  # closure only via /verify
    "Closed": set(),
}


@app.get("/api/capas")
def list_capas(status: str = "", q: str = "") -> list[dict]:
    with db.get_conn() as conn:
        sql = "SELECT * FROM capas WHERE 1=1"
        params: list = []
        if status:
            sql += " AND status = ?"
            params.append(status)
        if q:
            sql += " AND (title LIKE ? OR description LIKE ? OR ref LIKE ? OR root_cause LIKE ?)"
            params.extend([f"%{q}%"] * 4)
        sql += " ORDER BY id DESC"
        return [_with_meta(conn, r) for r in _rows(conn.execute(sql, params))]


@app.get("/api/capas/assignment-suggestions")
def capa_assignment(root_cause_category: str = "") -> list[dict]:
    with db.get_conn() as conn:
        return recommendations.capa_assignment_suggestions(conn, root_cause_category)


@app.get("/api/capas/{capa_id}")
def get_capa(capa_id: int) -> dict:
    with db.get_conn() as conn:
        rec = _with_meta(conn, _row(_get_or_404(conn, "capas", capa_id)))
        if rec["car_id"]:
            car = conn.execute("SELECT ref, title FROM cars WHERE id = ?", (rec["car_id"],)).fetchone()
            rec["car_ref"] = car["ref"] if car else None
        rec["verified_by_name"] = _owner_name(conn, rec.get("verified_by"))
        rec["history"] = _rows(conn.execute(
            "SELECT * FROM history WHERE record_type='capa' AND record_id=? ORDER BY id DESC", (capa_id,)))
        return rec


@app.post("/api/capas", status_code=201)
def create_capa(body: m.CapaIn) -> dict:
    with db.get_conn() as conn:
        if body.car_id is not None:
            _get_or_404(conn, "cars", body.car_id)
        ref = db.next_ref(conn, "capas", "CAPA")
        cur = conn.execute(
            """INSERT INTO capas (ref, title, description, car_id, rcca_method,
                   root_cause_category, due_date, owner_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (ref, body.title, body.description, body.car_id, body.rcca_method,
             body.root_cause_category, body.due_date, body.owner_id))
        db.log_history(conn, "capa", cur.lastrowid, "created", f"{ref}: {body.title}")
        return _with_meta(conn, _row(conn.execute(
            "SELECT * FROM capas WHERE id = ?", (cur.lastrowid,)).fetchone()))


@app.patch("/api/capas/{capa_id}")
def update_capa(capa_id: int, body: m.CapaUpdate) -> dict:
    with db.get_conn() as conn:
        rec = _row(_get_or_404(conn, "capas", capa_id))
        changes = {k: v for k, v in body.model_dump().items() if v is not None}
        if changes:
            sets = ", ".join(f"{k} = ?" for k in changes) + ", updated_at = datetime('now')"
            conn.execute(f"UPDATE capas SET {sets} WHERE id = ?", (*changes.values(), capa_id))
            db.log_history(conn, "capa", capa_id, "updated", ", ".join(changes))
        return _with_meta(conn, _row(conn.execute(
            "SELECT * FROM capas WHERE id = ?", (capa_id,)).fetchone()))


@app.post("/api/capas/{capa_id}/status")
def capa_status(capa_id: int, body: m.StatusChange) -> dict:
    with db.get_conn() as conn:
        rec = _row(_get_or_404(conn, "capas", capa_id))
        allowed = CAPA_TRANSITIONS.get(rec["status"], set())
        if body.status not in allowed:
            raise HTTPException(
                status_code=400,
                detail=f"cannot move CAPA from '{rec['status']}' to '{body.status}' (allowed: {sorted(allowed)}; closure happens via effectiveness verification)")
        if body.status == "Effectiveness Verification" and not rec["root_cause"]:
            raise HTTPException(status_code=400, detail="root cause required before effectiveness verification")
        conn.execute(
            "UPDATE capas SET status = ?, updated_at = datetime('now') WHERE id = ?",
            (body.status, capa_id))
        db.log_history(conn, "capa", capa_id, "status",
                       f"{rec['status']} -> {body.status}" + (f" ({body.note})" if body.note else ""),
                       body.changed_by)
        return _with_meta(conn, _row(conn.execute(
            "SELECT * FROM capas WHERE id = ?", (capa_id,)).fetchone()))


@app.post("/api/capas/{capa_id}/verify")
def verify_capa(capa_id: int, body: m.CapaVerification) -> dict:
    """Audit validation of RCCA effectiveness. Effective -> Closed; not -> rework."""
    with db.get_conn() as conn:
        rec = _row(_get_or_404(conn, "capas", capa_id))
        if rec["status"] != "Effectiveness Verification":
            raise HTTPException(status_code=400, detail="CAPA must be in Effectiveness Verification")
        new_status = "Closed" if body.effective else "Actions In Progress"
        closed_at = "datetime('now')" if body.effective else "NULL"
        conn.execute(
            f"""UPDATE capas SET status = ?, effective = ?, effectiveness_result = ?,
                   verified_by = ?, verified_at = datetime('now'),
                   closed_at = {closed_at}, updated_at = datetime('now')
                WHERE id = ?""",
            (new_status, 1 if body.effective else 0, body.effectiveness_result,
             body.verified_by, capa_id))
        db.log_history(conn, "capa", capa_id,
                       "verified-effective" if body.effective else "verified-not-effective",
                       body.effectiveness_result)
        return _with_meta(conn, _row(conn.execute(
            "SELECT * FROM capas WHERE id = ?", (capa_id,)).fetchone()))


@app.get("/api/capas/{capa_id}/rcca-suggestions")
def capa_rcca(capa_id: int) -> list[dict]:
    with db.get_conn() as conn:
        _get_or_404(conn, "capas", capa_id)
        return recommendations.capa_rcca_suggestions(conn, capa_id)


# ---------------------------------------------------------------- bulletins

@app.get("/api/bulletins")
def list_bulletins() -> list[dict]:
    with db.get_conn() as conn:
        return _rows(conn.execute("SELECT * FROM bulletins ORDER BY id DESC"))


@app.post("/api/bulletins", status_code=201)
def create_bulletin(body: m.BulletinIn) -> dict:
    """Targeted quality alert bulletin, optionally tied to a CAR."""
    with db.get_conn() as conn:
        if body.car_id is not None:
            _get_or_404(conn, "cars", body.car_id)
        ref = db.next_ref(conn, "bulletins", "QAB")
        cur = conn.execute(
            "INSERT INTO bulletins (ref, title, body, car_id, audience, issued_by) VALUES (?, ?, ?, ?, ?, ?)",
            (ref, body.title, body.body, body.car_id, body.audience, body.issued_by))
        db.log_history(conn, "bulletin", cur.lastrowid, "issued", f"{ref} to {body.audience}")
        db.send_notification(conn, "bulletin", cur.lastrowid, body.audience,
                             f"Quality alert {ref}: {body.title}")
        return _row(conn.execute("SELECT * FROM bulletins WHERE id = ?", (cur.lastrowid,)).fetchone())


# ------------------------------------------------- automated escalation run

@app.post("/api/run-escalation")
def run_escalation() -> dict:
    """Automated tracking and escalation: bump overdue open records one
    escalation level and notify owners. Intended to run on a schedule."""
    LEVELS = ["None", "Level 1", "Level 2", "Executive"]
    escalated = []
    with db.get_conn() as conn:
        for table, rtype in (("escapes", "escape"), ("cars", "car")):
            rows = _rows(conn.execute(
                f"SELECT * FROM {table} WHERE status != 'Closed' AND due_date IS NOT NULL AND due_date < ?",
                (date.today().isoformat(),)))
            for r in rows:
                idx = LEVELS.index(r["escalation_level"]) if r["escalation_level"] in LEVELS else 0
                if idx >= len(LEVELS) - 1:
                    continue
                new_level = LEVELS[idx + 1]
                conn.execute(
                    f"UPDATE {table} SET escalation_level = ?, updated_at = datetime('now') WHERE id = ?",
                    (new_level, r["id"]))
                recipient = _owner_name(conn, r["owner_id"]) or "quality-management"
                db.send_notification(conn, rtype, r["id"], recipient,
                                     f"{r['ref']} is overdue (due {r['due_date']}); escalated to {new_level}")
                db.log_history(conn, rtype, r["id"], "escalated", f"overdue -> {new_level}")
                escalated.append({"ref": r["ref"], "type": rtype, "new_level": new_level})
    return {"escalated": escalated, "count": len(escalated)}


# ------------------------------------------------------------- CSV import

IMPORT_COLUMNS = {
    "escapes": ["title", "description", "escape_type", "customer", "program", "part_number",
                "severity", "likelihood", "containment_plan", "due_date", "status"],
    "cars": ["title", "description", "car_type", "supplier", "severity", "due_date", "status"],
    "capas": ["title", "description", "rcca_method", "root_cause_category", "root_cause",
              "corrective_action", "preventive_action", "due_date", "status"],
}


@app.get("/api/import/template/{entity}")
def import_template(entity: str) -> dict:
    if entity not in IMPORT_COLUMNS:
        raise HTTPException(status_code=404, detail="unknown entity")
    return {"entity": entity, "columns": IMPORT_COLUMNS[entity]}


@app.post("/api/import/{entity}")
async def import_csv(entity: str, file: UploadFile) -> dict:
    """Migrate existing spreadsheet data. Expects a CSV with a header row;
    only recognized columns are used, the rest are ignored."""
    if entity not in IMPORT_COLUMNS:
        raise HTTPException(status_code=404, detail="unknown entity")
    raw = (await file.read()).decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(raw))
    allowed = set(IMPORT_COLUMNS[entity])
    imported, errors = 0, []
    with db.get_conn() as conn:
        for i, row in enumerate(reader, start=2):
            data = {k.strip().lower(): (v or "").strip() for k, v in row.items() if k}
            data = {k: v for k, v in data.items() if k in allowed}
            if not data.get("title"):
                errors.append(f"row {i}: missing title")
                continue
            try:
                if entity == "escapes":
                    sev = int(data.get("severity") or 3)
                    lik = int(data.get("likelihood") or 2)
                    score, level = rating.rate(max(1, min(4, sev)), max(1, min(4, lik)))
                    ref = db.next_ref(conn, "escapes", "ESC")
                    cur = conn.execute(
                        """INSERT INTO escapes (ref, title, description, escape_type, customer,
                               program, part_number, severity, likelihood, rating_score,
                               escalation_level, containment_plan, due_date, status)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (ref, data["title"], data.get("description", ""),
                         data.get("escape_type") or "internal", data.get("customer", ""),
                         data.get("program", ""), data.get("part_number", ""),
                         max(1, min(4, sev)), max(1, min(4, lik)), score, level,
                         data.get("containment_plan", ""), data.get("due_date") or None,
                         data.get("status") or "Open"))
                    db.log_history(conn, "escape", cur.lastrowid, "imported", f"{ref} from {file.filename}")
                elif entity == "cars":
                    ref = db.next_ref(conn, "cars", "CAR")
                    cur = conn.execute(
                        """INSERT INTO cars (ref, title, description, car_type, supplier,
                               severity, due_date, status)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                        (ref, data["title"], data.get("description", ""),
                         data.get("car_type") or "internal", data.get("supplier", ""),
                         max(1, min(4, int(data.get("severity") or 3))),
                         data.get("due_date") or None, data.get("status") or "Draft"))
                    db.log_history(conn, "car", cur.lastrowid, "imported", f"{ref} from {file.filename}")
                else:
                    ref = db.next_ref(conn, "capas", "CAPA")
                    cur = conn.execute(
                        """INSERT INTO capas (ref, title, description, rcca_method,
                               root_cause_category, root_cause, corrective_action,
                               preventive_action, due_date, status)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (ref, data["title"], data.get("description", ""),
                         data.get("rcca_method") or "5-Why", data.get("root_cause_category", ""),
                         data.get("root_cause", ""), data.get("corrective_action", ""),
                         data.get("preventive_action", ""), data.get("due_date") or None,
                         data.get("status") or "Open"))
                    db.log_history(conn, "capa", cur.lastrowid, "imported", f"{ref} from {file.filename}")
                imported += 1
            except (ValueError, sqlite3.Error) as exc:
                errors.append(f"row {i}: {exc}")
    return {"imported": imported, "errors": errors}


# ------------------------------------------------------------------- static

@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
