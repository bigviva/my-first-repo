"""Seed the database with demo data so the app is explorable out of the box.

Run: python -m app.seed
"""
from . import database as db
from . import rating


def seed() -> None:
    db.init_db()
    with db.get_conn() as conn:
        if conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]:
            print("Database already has data; skipping seed.")
            return

        users = [
            ("Dana Reyes", "dana.reyes@example.com", "Quality Engineering"),
            ("Marcus Cole", "marcus.cole@example.com", "Supplier Quality"),
            ("Priya Nair", "priya.nair@example.com", "Manufacturing Engineering"),
            ("Tom Alvarez", "tom.alvarez@example.com", "Quality Assurance"),
        ]
        for name, email, dept in users:
            conn.execute("INSERT INTO users (name, email, department) VALUES (?, ?, ?)",
                         (name, email, dept))

        escapes = [
            ("Cracked bracket shipped to customer", "Customer reported hairline crack in mounting bracket on delivered unit.",
             "external", "Northrop", "Falcon", "BRK-2231", 4, 2, "Quarantined remaining lot, 100% visual inspection added.", "2026-07-15", "Closed"),
            ("Wrong torque spec applied on line 3", "Operators used superseded torque spec from outdated work instruction.",
             "internal", "", "Atlas", "ASM-1102", 3, 3, "Line stopped, affected units re-torqued and verified.", "2026-08-20", "In Progress"),
            ("Unsealed connector found at receiving inspection", "Supplier shipped connectors without conformal seal.",
             "external", "Raytheon", "Sentinel", "CON-8804", 2, 2, "", "2026-08-30", "Open"),
        ]
        for title, desc, etype, cust, prog, pn, sev, lik, plan, due, status in escapes:
            score, level = rating.rate(sev, lik)
            ref = db.next_ref(conn, "escapes", "ESC")
            cur = conn.execute(
                """INSERT INTO escapes (ref, title, description, escape_type, customer, program,
                       part_number, severity, likelihood, rating_score, escalation_level,
                       containment_plan, due_date, status, owner_id,
                       closed_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (ref, title, desc, etype, cust, prog, pn, sev, lik, score, level,
                 plan, due, status, 1, "2026-07-20 10:00:00" if status == "Closed" else None))
            db.log_history(conn, "escape", cur.lastrowid, "created", f"{ref}: {title} (seed)")

        cars = [
            ("Bracket crack — supplier process control", "Supplier stamping process producing micro-cracks; require process control plan update.",
             "external", "Apex Metalforms", 1, 4, "2026-07-30", "Closed",
             "Updated die maintenance interval from 50k to 20k cycles, added eddy-current check at final inspection. Verified on 3 lots.",
             "Response verified against lot data; accepted."),
            ("Torque spec document control", "Superseded work instruction remained on shop floor; document control gap.",
             "internal", "", 2, 3, "2026-09-10", "Issued", "", ""),
            ("Connector sealing nonconformance", "Supplier skipped conformal seal operation on lot 44B.",
             "external", "ConnectPro", 3, 3, "2026-09-01", "Draft", "", ""),
        ]
        for title, desc, ctype, supplier, escape_id, sev, due, status, resp, decision in cars:
            ref = db.next_ref(conn, "cars", "CAR")
            cur = conn.execute(
                """INSERT INTO cars (ref, title, description, car_type, supplier, escape_id,
                       severity, due_date, status, response_text, response_decision_notes,
                       validated_by, validated_at, response_submitted_at, closed_at, owner_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (ref, title, desc, ctype, supplier, escape_id, sev, due, status, resp, decision,
                 2 if status != "Draft" else None,
                 "2026-07-01 09:00:00" if status != "Draft" else None,
                 "2026-07-10 14:00:00" if resp else None,
                 "2026-07-25 16:00:00" if status == "Closed" else None, 2))
            db.log_history(conn, "car", cur.lastrowid, "created", f"{ref}: {title} (seed)")

        capas = [
            ("Die maintenance program overhaul", "Systemic fix for stamping micro-cracks across all supplier dies.",
             1, "8D", "Supplier", "Die wear beyond tolerance due to maintenance interval based on time, not cycle count.",
             "Cycle-count-based die maintenance with automated counters.",
             "Extend cycle-count maintenance to all stamping suppliers; add to supplier quality manual.",
             "2026-08-01", "Closed", 1, "Zero crack escapes across 6 lots post-implementation.", 4, 2),
            ("Shop floor document control system", "Prevent superseded work instructions from remaining in use.",
             2, "5-Why", "Documentation", "No forced expiry of printed work instructions; revision control manual.",
             "Electronic work instructions at each station pulling current revision only.",
             "Quarterly document control audits on all lines.",
             "2026-10-01", "Actions In Progress", None, "", None, 3),
        ]
        for (title, desc, car_id, method, cat, rc, ca, pa, due, status,
             effective, result, verifier, owner) in capas:
            ref = db.next_ref(conn, "capas", "CAPA")
            cur = conn.execute(
                """INSERT INTO capas (ref, title, description, car_id, rcca_method,
                       root_cause_category, root_cause, corrective_action, preventive_action,
                       due_date, status, effective, effectiveness_result, verified_by,
                       verified_at, closed_at, owner_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (ref, title, desc, car_id, method, cat, rc, ca, pa, due, status,
                 effective, result, verifier,
                 "2026-08-05 11:00:00" if effective is not None else None,
                 "2026-08-05 11:00:00" if status == "Closed" else None, owner))
            db.log_history(conn, "capa", cur.lastrowid, "created", f"{ref}: {title} (seed)")

        ref = db.next_ref(conn, "bulletins", "QAB")
        cur = conn.execute(
            "INSERT INTO bulletins (ref, title, body, car_id, audience, issued_by) VALUES (?, ?, ?, ?, ?, ?)",
            (ref, "Verify torque specs against current revision",
             "All operators: confirm work instruction revision matches the document portal before each shift. Related to CAR-0002.",
             2, "Manufacturing - All Lines", 4))
        db.log_history(conn, "bulletin", cur.lastrowid, "issued", f"{ref} (seed)")
        print("Seeded demo data.")


if __name__ == "__main__":
    seed()
