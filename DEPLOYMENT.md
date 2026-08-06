# Production deployment guide

The path from this repo to a company-wide deployment, in order. Items marked
**[built]** are implemented; items marked **[IT]** need your IT organization.

## 1. Pilot deployment (do this now)

**[built]** The app ships with login, roles, Docker packaging, scheduled
escalation, and SMTP notifications.

```bash
cp .env.example .env      # set ADMIN_EMAIL / ADMIN_PASSWORD at minimum
docker compose up -d --build
```

Open http://localhost:8000, sign in as the admin, and create accounts for the
pilot team under **Users**. Data persists in the `cat-data` Docker volume.

Without Docker: `pip install -r requirements.txt && uvicorn app.main:app`.

### Roles

| Role | Can |
|---|---|
| `admin` | everything, plus user management |
| `quality` | create/edit/transition all records |
| `viewer` | read-only on everything internal |
| `supplier` | see only CARs addressed to their `supplier_name`; submit responses |

### Security notes for the pilot

- Serve behind HTTPS (put nginx/Caddy or your company's reverse proxy in front).
- Sessions are HttpOnly cookies with a 12-hour lifetime; passwords are PBKDF2-hashed.
- Set a strong `ADMIN_PASSWORD` before first boot; the dev fallback prints a
  warning at startup.

## 2. Single sign-on **[IT]**

Ask IT to register an app in Microsoft Entra (Azure AD) with OIDC.
The integration point is deliberately small: `app/auth.py` — an OIDC callback
would look up/create the user row by email and call `create_session()`, exactly
as `/api/auth/login` does. Role assignment can map from Entra groups.
Supplier accounts typically stay on local credentials or a separate B2B tenant.

What to request from IT: client ID, client secret, tenant ID, redirect URI
approval, and a group-to-role mapping decision.

## 3. PostgreSQL **[IT provisions, code change is contained]**

SQLite is fine for a pilot (single writer, file on disk, snapshot backups).
Move to PostgreSQL when the pilot widens: the SQL in `app/database.py` uses a
small SQLite dialect surface (`datetime('now')`, `julianday`, `AUTOINCREMENT`,
`PRAGMA`) — the migration is mechanical and the schema is portable. Request a
managed PostgreSQL instance with automated backups.

## 4. Operations checklist before wide rollout

- [ ] HTTPS via company reverse proxy / load balancer
- [ ] Daily database backups tested with a restore drill
- [ ] Log aggregation (uvicorn access logs + app stdout)
- [ ] Uptime monitoring on `/api/dashboard` (any 200 with a valid session)
- [ ] SMTP relay approved for the notification sender address
- [ ] Data migrated from spreadsheets via the Import tab, spot-checked
- [ ] Pilot feedback incorporated (2+ weeks of real use)
- [ ] Pagination added to list endpoints if record counts exceed ~2,000

## 5. Known not-yet-built (next development phases)

- File attachments on records (evidence photos, 8D reports)
- OIDC/SSO login flow (the seam exists; the flow does not)
- PostgreSQL support (see §3)
- Report exports (CSV/PDF of filtered lists)
- E-signature-grade approval records, if AS9100 auditors require them
