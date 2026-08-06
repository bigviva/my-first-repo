# User guide

For pilot users. You need an account (ask your admin) and the app URL.

## Signing in

Enter your email and password. Your session lasts 12 hours; use **Sign out**
(top right) on shared machines. What you can see and do depends on your role —
if a button described here isn't visible, your role doesn't include it.

## The three record types, in one sentence each

- **Escape** — a defect that got past a control (internally or to a customer):
  contain it, rate it, drive it to closure.
- **CAR** (Corrective Action Report) — a formal demand that a responsible
  party (often a supplier) fix a specific problem and prove it.
- **CAPA** — the systemic fix: root cause analysis, corrective and preventive
  actions, verified effective before it can close.

They chain: an escape can spawn CARs ("Raise CAR from this escape"), and a
CAR can spawn CAPAs ("Create CAPA from this CAR"). Use the links — the chain
is what makes the history auditable.

## Working an escape

1. **Escapes → + New Escape.** Pick internal/external, set severity (how bad)
   and likelihood (how often it could recur). The rating and escalation level
   compute automatically — you don't argue about them, the matrix decides.
2. Write the **containment plan** (what stops the bleeding today). The system
   will not let the escape close without one.
3. Move it through its statuses with the buttons on the detail page. Every
   move is logged with your name.
4. **Send notification** records (and emails, if configured) a message to a
   person or team — use it for customer notifications so there's a record.

## Working a CAR

1. Create it (often from an escape). It starts as a **Draft**.
2. **Validate for issuance** — a second look before it goes out: right scope,
   right supplier, severity justified, not a duplicate. Reject leaves it in
   draft with your notes.
3. **Issue** — the supplier (or internal owner) is notified with the due date.
4. The responsible party **submits a response** (root cause + what they did).
   Suppliers with accounts can do this themselves — they only see their own CARs.
5. **Accept or reject** the response. Rejection sends it back with your notes;
   they resubmit. Acceptance unlocks **Close CAR**.
6. **Response recommendations** shows how similar past CARs were successfully
   answered — useful for judging whether a response is up to standard.
7. **Issue quality alert bulletin** pushes a targeted heads-up ("Line 3:
   check torque specs") tied to this CAR, to a named audience.

## Working a CAPA

1. Create it (often from a CAR). Pick the RCCA method you're using
   (5-Why, Fishbone, 8D…).
2. Move to **RCCA In Progress** and fill in the root cause, corrective
   action, and preventive action (Edit RCCA / actions). Try **RCCA
   suggestions** — it surfaces root causes from similar CAPAs that were
   *verified effective*.
3. Move to **Actions In Progress** while the fixes land.
4. Move to **Effectiveness Verification** (requires a root cause on file).
   An auditor records the verification with objective evidence:
   - **Effective** → the CAPA closes.
   - **Not effective** → it goes back to Actions In Progress, and the failed
     verification stays on the record.
5. When creating a CAPA, **Suggest owner** ranks people by their track record
   of effective closures in that root-cause category, balanced against their
   current open load.

## Dashboard & Analytics

- **Dashboard**: live counts — open, closed, overdue, escalated — plus recent
  activity across the system.
- **Analytics**: 12-month created-vs-closed trend, average days to close,
  aging of open records, escapes by customer, CARs by supplier, root cause
  Pareto, CAR first-pass acceptance, CAPA effectiveness rate.

Overdue records escalate automatically overnight: each sweep bumps them one
level (None → Level 1 → Level 2 → Executive) and notifies the owner.

## Import (migrating your spreadsheets)

Export each tracking sheet as CSV **with a header row**, then Import tab →
pick the record type → upload. Column names match case-insensitively;
unrecognized columns are ignored; rows with problems are reported by row
number and skipped (fix and re-upload just those). The recognized columns
are listed on the page.

## Admins

**Users** tab: create accounts (set role + initial password), deactivate on
departure (kills their session immediately). Supplier accounts need the
`supplier_name` to exactly match the Supplier field on their CARs.
