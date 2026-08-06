# Architecture

A deliberately small system: one FastAPI process serving both a JSON API and a
dependency-free single-page frontend, backed by SQLite. No build step, no
message queue, no cache layer — every piece earns its place, and the pieces
that will change at scale (database, identity provider, notification channel)
are isolated behind small seams.

```
 Browser (static/app.js — vanilla JS SPA)
    │  fetch() with session cookie
    ▼
 FastAPI (app/main.py — routes + workflow rules)
    │            │              │
    ▼            ▼              ▼
 app/auth.py  app/rating.py  app/recommendations.py
 (sessions,   (escape rating (similarity over
  roles)       matrix)        historical records)
    │            │              │
    └────────────┴──────┬───────┘
                        ▼
              app/database.py (SQLite, schema,
              history log, notification log)
                        │
                        ▼
              app/notify.py (SMTP delivery,
              best-effort, log is source of truth)
```

## Module map

| Module | Responsibility | Depends on |
|---|---|---|
| `app/main.py` | HTTP routes, workflow/status rules, role enforcement per route, CSV import, escalation sweep + nightly scheduler | everything below |
| `app/auth.py` | Password hashing (PBKDF2), server-side sessions, role dependencies (`current_user`, `require_writer`, `require_admin`, `forbid_supplier`), admin bootstrap | `database` |
| `app/database.py` | Schema (single source of truth), column migrations for existing DBs, connection management, `log_history`, `send_notification` | `notify` |
| `app/models.py` | Pydantic request bodies (input validation) | — |
| `app/rating.py` | The 4×4 severity × likelihood rating matrix and escalation thresholds | — |
| `app/recommendations.py` | Cosine similarity over token counts; CAR response recs, CAPA RCCA assist, assignment suggestions | — |
| `app/analytics.py` | Dashboard/analytics aggregations (trends, cycle times, aging, Pareto) | — |
| `app/notify.py` | SMTP email delivery, recipient resolution (email / user name) | — |
| `app/seed.py` | Demo data + demo accounts for local evaluation | `database`, `auth`, `rating` |
| `static/` | SPA: router, views, forms, SVG charts, login screen | the API only |

## Data model

Core entities and their linkage (an escape can spawn CARs; a CAR can spawn
CAPAs and bulletins):

```
users ──────────┐ (owner_id / validated_by / verified_by / issued_by)
                ▼
escapes ──< cars ──< capas
              │
              └──< bulletins

history        (record_type, record_id) — append-only audit trail, all entities
notifications  (record_type, record_id) — outbound message log, all entities
sessions       (token → user_id) — server-side login sessions
```

Reference numbers (`ESC-0001`, `CAR-0001`, `CAPA-0001`, `QAB-0001`) are
assigned at creation from a per-table counter and never reused.

All timestamps are stored as UTC text (`datetime('now')`). Dates that carry
no time (due dates) are `YYYY-MM-DD` strings, compared lexically — valid
because the format is fixed-width.

## Workflow state machines

Transitions outside these edges are rejected with HTTP 400. This is the core
value over spreadsheets: the tool won't let a record skip its gates.

**Escape** — closure requires a containment plan:

```
Open ──> Containment ──> In Progress ──> Pending Closure ──> Closed
  │                          ▲    │                            │
  └──────────────────────────┘    └──── (back to In Progress)  │
  └─> Closed (trivial escapes)       Closed ─> In Progress (reopen)
```

**CAR** — cannot be issued without validation; closure only after an accepted
response:

```
Draft ──validate──> Validated ──issue──> Issued ──respond──> Response Submitted
                                            ▲                     │ decision
                                            │              ┌──────┴──────┐
                                        (resubmit)         ▼             ▼
                                            └──── Response Rejected  Response Accepted
                                                                         │ close
                                                                         ▼
                                                                       Closed
```

**CAPA** — closure happens *only* through effectiveness verification, and a
root cause is required before verification can begin:

```
Open ──> RCCA In Progress ──> Actions In Progress ──> Effectiveness Verification
                                    ▲                        │ verify
                                    │                 ┌──────┴──────┐
                                    └── not effective ┘             ▼
                                                              Closed (effective)
```

## Security model

- **Sessions**: opaque 256-bit tokens in an HttpOnly, SameSite=Lax cookie,
  stored server-side with a 12-hour expiry. Logout and deactivation delete
  the user's sessions immediately.
- **Passwords**: PBKDF2-HMAC-SHA256, 240k iterations, per-user salt.
- **Roles** (enforced server-side on every route; the UI hiding buttons is
  convenience, not security):
  - `admin` — everything + user management
  - `quality` — read/write all records
  - `viewer` — read-only on internal data
  - `supplier` — only CARs whose `supplier` field matches their
    `supplier_name`; may submit responses to those CARs; everything else 403s.
    The list query filters server-side, so scoping holds even for search.
- **SQL**: all queries parameterized. Dynamic fragments (`SET` clauses)
  interpolate *column names from a fixed allowlist* (the Pydantic model
  fields), never values.
- **XSS**: every user-supplied string rendered by the SPA passes through
  `esc()` (HTML entity escaping).
- **SSO seam**: an OIDC callback would resolve/create the user row and call
  `auth.create_session()` — the same path `/api/auth/login` uses. Nothing
  else changes.

## Background work

One asyncio task (started in the FastAPI lifespan) runs the overdue
escalation sweep every `ESCALATION_INTERVAL_HOURS` (default 24, `0`
disables). Each sweep bumps overdue open escapes/CARs one escalation level
and writes owner notifications. The sweep is also exposed as
`POST /api/run-escalation` for manual runs and tests. It is idempotent per
day in effect: a record already at `Executive` is not bumped further.

## Recommendations ("AI assist" features)

Deliberately no external AI dependency: plain cosine similarity over
stop-word-filtered token counts (`app/recommendations.py`). Quality scales
with the history in the database — which is the point: the system gets
smarter as the team uses it, works offline, and every suggestion is
traceable to a real prior record shown alongside its score. If an LLM
integration is wanted later, these endpoints are the natural seam.

## Known scale limits (accepted for pilot)

- SQLite single-writer: fine for tens of concurrent users; move to
  PostgreSQL for org-wide rollout (see DEPLOYMENT.md §3).
- List endpoints return all rows (no pagination) — acceptable to ~2,000
  records per entity; add `LIMIT/OFFSET` before that.
- Recommendation scoring loads candidate rows into memory — fine to tens of
  thousands of records.
- `next_ref` derives numbers from `COUNT(*)`; safe under SQLite's writer
  serialization, needs a sequence when PostgreSQL lands.
