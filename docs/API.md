# API reference

Every endpoint is under `/api`. Interactive docs (with request schemas and a
try-it console) are auto-generated at `/docs`; this file is the curated
reference with role requirements and workflow notes.

**Authentication**: all endpoints except `POST /api/auth/login` require a
session cookie obtained by logging in. Unauthenticated requests get `401`.

**Roles** (least → most privileged): `supplier` → `viewer` → `quality` →
`admin`. In the tables below, the *Role* column is the minimum requirement:

- *any* — any signed-in user
- *internal* — any role except `supplier`
- *writer* — `quality` or `admin`
- *admin* — `admin` only

Errors are JSON: `{"detail": "..."}` with 400 (bad transition/validation),
401 (no session), 403 (role), 404 (not found), 409 (conflict).

## Auth

| Method & path | Role | Notes |
|---|---|---|
| `POST /api/auth/login` | — | `{email, password}` → sets session cookie, returns the user |
| `POST /api/auth/logout` | any | Destroys all of the caller's sessions |
| `GET /api/auth/me` | any | Current user (no password hash) |
| `POST /api/auth/password` | any | `{current_password, new_password}`; invalidates sessions |

## Users

| Method & path | Role | Notes |
|---|---|---|
| `GET /api/users` | internal | All users, password hashes stripped |
| `POST /api/users` | admin | `{name, email, department?, role?, password?, supplier_name?}` |
| `PATCH /api/users/{id}` | admin | Any subset; `active: false` kills sessions immediately |

## Escapes

| Method & path | Role | Notes |
|---|---|---|
| `GET /api/escapes` | internal | Filters: `status`, `escape_type`, `q` (search) |
| `POST /api/escapes` | writer | Rating + escalation computed from `severity` × `likelihood`; high ratings auto-notify |
| `GET /api/escapes/{id}` | internal | Includes linked CARs, history, notifications |
| `PATCH /api/escapes/{id}` | writer | Re-rates when severity/likelihood change |
| `POST /api/escapes/{id}/status` | writer | `{status, note?}`; containment plan required to close |
| `POST /api/escapes/{id}/notify` | writer | `{recipient, message}` — logs + emails if SMTP configured |

## CARs

| Method & path | Role | Notes |
|---|---|---|
| `GET /api/cars` | any | Suppliers see only their own CARs (server-side filter); `status`, `car_type`, `q` |
| `POST /api/cars` | writer | Created as `Draft`; optional `escape_id` link |
| `GET /api/cars/{id}` | any* | *Suppliers: own CARs only. Includes CAPAs, bulletins, history |
| `PATCH /api/cars/{id}` | writer | Basic fields |
| `POST /api/cars/{id}/validate` | writer | `{approved, validated_by?, validation_notes?}`; the gate before issuance |
| `POST /api/cars/{id}/issue` | writer | Notifies the supplier/responsible party |
| `POST /api/cars/{id}/respond` | writer or own supplier | `{response_text}`; from `Issued` or `Response Rejected` |
| `POST /api/cars/{id}/decision` | writer | `{accept, notes?}`; reject notifies the supplier |
| `POST /api/cars/{id}/close` | writer | Only from `Response Accepted` |
| `GET /api/cars/{id}/response-recommendations` | internal | Similar closed CARs with accepted responses |

## CAPAs

| Method & path | Role | Notes |
|---|---|---|
| `GET /api/capas` | internal | Filters: `status`, `q` |
| `POST /api/capas` | writer | Optional `car_id` link |
| `GET /api/capas/assignment-suggestions` | internal | `?root_cause_category=` — owners ranked by effective-closure track record vs. open load |
| `GET /api/capas/{id}` | internal | Includes history, verifier name |
| `PATCH /api/capas/{id}` | writer | RCCA fields, actions, owner, due date |
| `POST /api/capas/{id}/status` | writer | Root cause required to enter Effectiveness Verification; direct close rejected |
| `POST /api/capas/{id}/verify` | writer | `{effective, effectiveness_result?, verified_by?}` — effective → Closed, else back to rework |
| `GET /api/capas/{id}/rcca-suggestions` | internal | Root causes/actions from similar *effective* CAPAs |

## Bulletins, dashboard, analytics, escalation

| Method & path | Role | Notes |
|---|---|---|
| `GET /api/bulletins` | internal | Newest first |
| `POST /api/bulletins` | writer | `{title, body, car_id?, audience?, issued_by?}`; notifies the audience |
| `GET /api/dashboard` | internal | Open/closed/overdue/escalated counts, recent activity |
| `GET /api/analytics` | internal | 12-month trend, cycle times, aging, Pareto, rates |
| `POST /api/run-escalation` | writer | Manual overdue sweep (also runs nightly) |

## Import

| Method & path | Role | Notes |
|---|---|---|
| `GET /api/import/template/{entity}` | writer | Recognized CSV columns for `escapes` / `cars` / `capas` |
| `POST /api/import/{entity}` | writer | Multipart CSV upload; returns `{imported, errors[]}` with row numbers |
