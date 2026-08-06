# Corrective Actions Tracking System

A self-contained web app for tracking quality escapes, Corrective Action
Reports (CARs), and Corrective and Preventive Actions (CAPA) — replacing
spreadsheet + SharePoint tracking with enforced workflows, linked records,
an audit trail, and built-in recommendations from historical data.

## What it covers

**Processing of Escapes**
- Internal / external (customer) escape repository with customer, program, and part number
- Common rating matrix: severity × likelihood → score → automatic escalation level
- Containment plan capture — closure is blocked until a containment plan exists
- Notification log per escape, plus automatic notifications on high ratings
- Enforced status workflow: Open → Containment → In Progress → Pending Closure → Closed

**Processing of CARs**
- Validation gate prior to issuance (a CAR cannot be issued from Draft)
- Internal / external (supplier) CARs, linkable to a source escape
- Response submission → accept/reject cycle, with rejection sending it back for rework
- Response recommendations mined from similar closed CARs with accepted responses
- Targeted quality alert bulletins tied to a CAR and an audience
- Overdue tracking with automated escalation sweep and notifications

**Processing of CAPA**
- RCCA capture: method (5-Why, Fishbone, 8D, …), root cause category, root cause,
  corrective and preventive actions
- RCCA assist: suggestions pulled from similar *historically effective* CAPAs
- Effectiveness verification gate: a CAPA can only close through an audit-style
  verification; "not effective" sends it back to rework and is recorded
- Assignment suggestions ranked by each owner's track record of effective
  closures in the same root-cause category, balanced against current workload

**Cross-cutting**
- Full record linkage: Escape → CAR → CAPA, plus bulletins per CAR
- Immutable history log on every record
- Dashboard with open/closed/overdue/escalated counts and CAPA effectiveness rate
- Analytics: 12-month created-vs-closed trend, average cycle times, open-record
  aging buckets, escapes by customer, CARs by supplier, root cause Pareto,
  escalation distribution, CAR first-pass acceptance rate (`/api/analytics`,
  rendered as dependency-free SVG charts on the Analytics tab)
- CSV import to migrate existing spreadsheet data (Escapes, CARs, CAPAs)

## Running it

```bash
pip install -r requirements.txt
python -m app.seed          # optional: load demo data
uvicorn app.main:app --reload
```

Open http://localhost:8000 — the UI is served from the same process.
Interactive API docs are at http://localhost:8000/docs.

Data is stored in `data/corrective_actions.db` (SQLite). Set `CAT_DB_PATH`
to use a different location.

## Migrating from spreadsheets

Export each tracking sheet to CSV with a header row and upload it on the
**Import** tab (or `POST /api/import/{escapes|cars|capas}`). Column names are
matched case-insensitively and unrecognized columns are ignored.
`GET /api/import/template/{entity}` lists the recognized columns.

## Tests

```bash
python -m pytest
```

## Architecture

- `app/main.py` — FastAPI routes and workflow rules (status transition enforcement)
- `app/database.py` — SQLite schema, history log, notification log
- `app/rating.py` — the common escape rating / escalation matrix
- `app/recommendations.py` — keyword-similarity recommendations over historical records
- `static/` — dependency-free single-page frontend (no build step)
- `tests/` — end-to-end API tests for every workflow

Notifications are recorded in the database; wiring them to email/Teams is a
single integration point in `app/database.py:send_notification`.
