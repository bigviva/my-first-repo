# IT request tickets — ready to paste

Four independent requests for taking the Corrective Actions Tracking System
to production. File them in parallel; none blocks another. Replace the
[bracketed] placeholders before submitting. Attach or link `DEPLOYMENT.md`
and `docs/ARCHITECTURE.md` (security model section) to each.

---

## Ticket 1 — Application hosting for internal quality tool

**Title:** Hosting request: Corrective Actions Tracking System (internal web app)

**Priority:** Medium

**Description:**
The Quality organization has a validated internal web application replacing
spreadsheet/SharePoint tracking of quality escapes, corrective action
reports (CARs), and CAPAs. We are requesting standard internal hosting.

**Specific request:**
- One small Linux VM or container hosting slot: 2 vCPU, 4 GB RAM, 20 GB
  disk (or the standard smallest tier)
- HTTPS exposure behind the standard internal reverse proxy / load
  balancer at an internal hostname, e.g. `corrective-actions.[company].com`
- A persistent volume or directory for file attachments (evidence uploads),
  included in backups
- The application ships as a Docker image (Dockerfile in the repository);
  it can also run as a plain systemd service if preferred

**Notes:** Stateless single process; no inbound access from outside the
corporate network required. Expected load is light (a few hundred internal
users, low concurrency). Architecture and security documentation available
in the repository.

---

## Ticket 2 — Managed PostgreSQL instance

**Title:** Database request: PostgreSQL for Corrective Actions Tracking System

**Priority:** Medium

**Description:**
Database backing for the internal quality application in Ticket 1. The
application currently runs on SQLite for its pilot; production requires a
managed PostgreSQL instance.

**Specific request:**
- One PostgreSQL instance, smallest standard tier (storage growth expected
  to be low — structured quality records, well under 10 GB for years)
- Automated daily backups with point-in-time recovery if available
- One application service account with rights limited to its own database
- Network access from the application host in Ticket 1 only

---

## Ticket 3 — Entra ID (Azure AD) app registration for SSO

**Title:** App registration request: OIDC SSO for Corrective Actions Tracking System

**Priority:** Medium

**Description:**
Single sign-on for the internal quality application in Ticket 1, so
employees use their standard company credentials and offboarding is
automatic.

**Specific request:**
- An Entra ID app registration (web application, OIDC authorization code flow)
- Redirect URI: `https://corrective-actions.[company].com/api/auth/oidc/callback`
- Client ID and client secret delivered via the standard secrets process
- Standard claims: email, name, and group membership
- A decision with us on group-to-role mapping — the app has four roles
  (admin, quality read/write, read-only viewer, external supplier); we
  propose mapping two existing security groups to admin and quality, with
  all other authenticated employees as viewers. Supplier accounts remain
  on local credentials (external parties, no Entra identities).

---

## Ticket 4 — SMTP relay approval

**Title:** SMTP relay request: notification sender for Corrective Actions Tracking System

**Priority:** Low

**Description:**
The quality application in Ticket 1 sends workflow notification emails
(overdue escalations, CAR issuance, response rejections) to internal users
and registered supplier contacts.

**Specific request:**
- Permission to relay through the internal SMTP gateway from the
  application host in Ticket 1
- A sender address: `corrective-actions@[company].com` (no-reply is fine)
- Expected volume: low tens of messages per day

---

*These artifacts pair with the one-page proposal document for
management/IT leadership. The repository's `DEPLOYMENT.md` describes the
full rollout sequence these tickets feed into.*
