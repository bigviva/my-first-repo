"""Analytics computations for the reporting dashboard.

Everything is computed from the live SQLite data — trends, cycle times,
aging, Pareto breakdowns, and quality rates.
"""
import sqlite3
from datetime import date


def _month_add(year: int, month: int, delta: int):
    m = (year * 12 + (month - 1)) + delta
    return m // 12, m % 12 + 1


def last_n_months(n: int = 12, today: date = None):
    today = today or date.today()
    months = []
    for i in range(n - 1, -1, -1):
        y, m = _month_add(today.year, today.month, -i)
        months.append(f"{y:04d}-{m:02d}")
    return months


def _monthly_counts(conn: sqlite3.Connection, table: str, column: str, months) -> dict:
    rows = conn.execute(
        f"""SELECT substr({column}, 1, 7) AS month, COUNT(*) AS n FROM {table}
            WHERE {column} IS NOT NULL GROUP BY month"""
    ).fetchall()
    by_month = {r["month"]: r["n"] for r in rows}
    return {m: by_month.get(m, 0) for m in months}


def _avg_cycle_days(conn: sqlite3.Connection, table: str):
    # MAX(..., 0) guards against imported legacy rows whose close date
    # precedes the recorded creation date
    row = conn.execute(
        f"""SELECT AVG(MAX(julianday(closed_at) - julianday(created_at), 0)) AS days
            FROM {table} WHERE closed_at IS NOT NULL"""
    ).fetchone()
    return round(row["days"], 1) if row["days"] is not None else None


AGING_BUCKETS = ("0-30", "31-60", "61-90", "90+")


def _aging(conn: sqlite3.Connection, table: str) -> dict:
    rows = conn.execute(
        f"""SELECT CAST(julianday('now') - julianday(created_at) AS INTEGER) AS age
            FROM {table} WHERE status != 'Closed'"""
    ).fetchall()
    buckets = dict.fromkeys(AGING_BUCKETS, 0)
    for r in rows:
        age = r["age"] or 0
        if age <= 30:
            buckets["0-30"] += 1
        elif age <= 60:
            buckets["31-60"] += 1
        elif age <= 90:
            buckets["61-90"] += 1
        else:
            buckets["90+"] += 1
    return buckets


def _top_group(conn: sqlite3.Connection, table: str, column: str, limit: int = 6):
    rows = conn.execute(
        f"""SELECT {column} AS label, COUNT(*) AS n FROM {table}
            WHERE {column} != '' GROUP BY {column} ORDER BY n DESC LIMIT ?""",
        (limit,),
    ).fetchall()
    return [{"label": r["label"], "count": r["n"]} for r in rows]


def compute(conn: sqlite3.Connection) -> dict:
    months = last_n_months(12)

    created = {m: 0 for m in months}
    closed = {m: 0 for m in months}
    for table in ("escapes", "cars", "capas"):
        for m, n in _monthly_counts(conn, table, "created_at", months).items():
            created[m] += n
        for m, n in _monthly_counts(conn, table, "closed_at", months).items():
            closed[m] += n

    root_cause = conn.execute(
        """SELECT root_cause_category AS label, COUNT(*) AS n FROM capas
           WHERE root_cause_category != '' GROUP BY root_cause_category
           ORDER BY n DESC"""
    ).fetchall()

    escalation = conn.execute(
        """SELECT escalation_level AS label, COUNT(*) AS n FROM (
               SELECT escalation_level FROM escapes WHERE status != 'Closed'
               UNION ALL
               SELECT escalation_level FROM cars WHERE status != 'Closed')
           GROUP BY escalation_level"""
    ).fetchall()
    esc_order = ["None", "Level 1", "Level 2", "Executive"]
    esc_map = {r["label"]: r["n"] for r in escalation}

    decided = conn.execute(
        """SELECT COUNT(*) AS n FROM cars
           WHERE status IN ('Response Accepted', 'Response Rejected', 'Closed')"""
    ).fetchone()["n"]
    rejected_ever = conn.execute(
        """SELECT COUNT(DISTINCT record_id) AS n FROM history
           WHERE record_type = 'car' AND action = 'response-rejected'"""
    ).fetchone()["n"]
    first_pass = None
    if decided:
        first_pass = round(100 * max(0, decided - rejected_ever) / decided)

    verified = conn.execute(
        "SELECT COUNT(*) AS n, SUM(effective) AS eff FROM capas WHERE effective IS NOT NULL"
    ).fetchone()
    effectiveness = round(100 * (verified["eff"] or 0) / verified["n"]) if verified["n"] else None

    return {
        "months": months,
        "monthly_created": [created[m] for m in months],
        "monthly_closed": [closed[m] for m in months],
        "cycle_time_days": {
            "escapes": _avg_cycle_days(conn, "escapes"),
            "cars": _avg_cycle_days(conn, "cars"),
            "capas": _avg_cycle_days(conn, "capas"),
        },
        "aging": {
            "buckets": list(AGING_BUCKETS),
            "escapes": [_aging(conn, "escapes")[b] for b in AGING_BUCKETS],
            "cars": [_aging(conn, "cars")[b] for b in AGING_BUCKETS],
            "capas": [_aging(conn, "capas")[b] for b in AGING_BUCKETS],
        },
        "escapes_by_customer": _top_group(conn, "escapes", "customer"),
        "cars_by_supplier": _top_group(conn, "cars", "supplier"),
        "root_cause_pareto": [{"label": r["label"], "count": r["n"]} for r in root_cause],
        "escalation_distribution": {
            "labels": esc_order,
            "counts": [esc_map.get(k, 0) for k in esc_order],
        },
        "car_first_pass_acceptance": first_pass,
        "capa_effectiveness_rate": effectiveness,
    }
