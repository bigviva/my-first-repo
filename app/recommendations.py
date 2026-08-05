"""Recommendation engine over historical records.

Implements the assist features from the Concern Module roadmap without any
external AI dependency: plain TF-IDF-style keyword similarity over the
closed/effective records already in the database.

- CAR response recommendation: surface accepted responses from the most
  similar closed CARs.
- CAPA RCCA assist: surface root causes / actions from historically
  *effective* CAPAs similar to the one being worked.
- CAPA assignment suggestion: rank owners by their track record of closing
  effective CAPAs in the same root-cause category, tie-broken by current
  open workload.
"""
import math
import re
import sqlite3
from collections import Counter

_STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "with", "is",
    "was", "were", "be", "been", "at", "by", "from", "as", "it", "this", "that",
    "not", "no", "we", "our", "has", "have", "had", "will", "are", "per",
}


def _tokens(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", (text or "").lower())
            if len(t) > 2 and t not in _STOPWORDS]


def similarity(text_a: str, text_b: str) -> float:
    """Cosine similarity over token counts."""
    ca, cb = Counter(_tokens(text_a)), Counter(_tokens(text_b))
    if not ca or not cb:
        return 0.0
    shared = set(ca) & set(cb)
    dot = sum(ca[t] * cb[t] for t in shared)
    norm = math.sqrt(sum(v * v for v in ca.values())) * math.sqrt(sum(v * v for v in cb.values()))
    return dot / norm if norm else 0.0


def car_response_recommendations(conn: sqlite3.Connection, car_id: int, limit: int = 3) -> list[dict]:
    car = conn.execute("SELECT * FROM cars WHERE id = ?", (car_id,)).fetchone()
    if car is None:
        return []
    query = f"{car['title']} {car['description']}"
    candidates = conn.execute(
        """SELECT id, ref, title, description, response_text FROM cars
           WHERE id != ? AND response_text != ''
             AND status IN ('Response Accepted', 'Closed')""",
        (car_id,),
    ).fetchall()
    scored = [
        {"car_ref": c["ref"], "car_title": c["title"], "response_text": c["response_text"],
         "score": round(similarity(query, f"{c['title']} {c['description']}"), 3)}
        for c in candidates
    ]
    scored = [s for s in scored if s["score"] > 0]
    scored.sort(key=lambda s: s["score"], reverse=True)
    return scored[:limit]


def capa_rcca_suggestions(conn: sqlite3.Connection, capa_id: int, limit: int = 3) -> list[dict]:
    capa = conn.execute("SELECT * FROM capas WHERE id = ?", (capa_id,)).fetchone()
    if capa is None:
        return []
    query = f"{capa['title']} {capa['description']}"
    candidates = conn.execute(
        """SELECT id, ref, title, description, root_cause, root_cause_category,
                  corrective_action, preventive_action FROM capas
           WHERE id != ? AND effective = 1 AND root_cause != ''""",
        (capa_id,),
    ).fetchall()
    scored = [
        {"capa_ref": c["ref"], "capa_title": c["title"], "root_cause": c["root_cause"],
         "root_cause_category": c["root_cause_category"],
         "corrective_action": c["corrective_action"], "preventive_action": c["preventive_action"],
         "score": round(similarity(query, f"{c['title']} {c['description']}"), 3)}
        for c in candidates
    ]
    scored = [s for s in scored if s["score"] > 0]
    scored.sort(key=lambda s: s["score"], reverse=True)
    return scored[:limit]


def capa_assignment_suggestions(conn: sqlite3.Connection, root_cause_category: str = "",
                                limit: int = 3) -> list[dict]:
    users = conn.execute("SELECT * FROM users").fetchall()
    results = []
    for u in users:
        effective_closed = conn.execute(
            """SELECT COUNT(*) AS n FROM capas
               WHERE owner_id = ? AND effective = 1
                 AND (? = '' OR root_cause_category = ?)""",
            (u["id"], root_cause_category, root_cause_category),
        ).fetchone()["n"]
        open_load = conn.execute(
            "SELECT COUNT(*) AS n FROM capas WHERE owner_id = ? AND status != 'Closed'",
            (u["id"],),
        ).fetchone()["n"]
        results.append({
            "user_id": u["id"], "name": u["name"], "department": u["department"],
            "effective_capas_closed": effective_closed, "open_capa_load": open_load,
            "score": round(effective_closed - 0.5 * open_load, 2),
        })
    results.sort(key=lambda r: (r["score"], r["effective_capas_closed"]), reverse=True)
    return results[:limit]
