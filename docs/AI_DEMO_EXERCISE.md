# AI demo exercise: from requirements to working prototype in one session

**Purpose:** show a colleague what AI-assisted development actually does — not
autocomplete, but the full arc: read messy requirements, reason about them,
propose a design, explain it in plain language, and then *build a working,
testable application*. This repository is a reference implementation produced
exactly this way; the exercise below lets someone reproduce the journey
themselves in Codex (or any capable AI coding tool — Claude Code, Cursor,
etc.).

**What you need:** access to an AI coding assistant that can create and run
files, ~30–60 minutes, and nothing else. No setup, no starter code.

**How to run it:** paste the prompts below into the assistant **one stage at
a time**, in order. The staging is the point — you'll watch it understand
before it plans, plan before it builds. Resist pasting everything at once the
first time; the conversation is the demo.

---

## The requirements (paste this with Stage 1)

This is a real-world style requirement set, distilled from an enterprise
quality-management roadmap ("Concern Module"). It is deliberately terse and
jargon-heavy — exactly what a developer usually gets handed.

```text
We track quality concerns in spreadsheets and SharePoint today and need a
real application. Three connected record types:

PROCESSING OF ESCAPES
- Customer escape notification repository
- Internal / external escape creation and management
- Common escape rating / escalation process
- Escape tracking to closure
- Escape containment plan and notifications

PROCESSING OF CARs (Corrective Action Reports)
- Validation of CAR prior to issuance
- Internal / external CAR creation and management
- CAR escalation and tracking to closure
- Automated CAR response recommendation
- Targeted quality alert bulletins to impacted employees
- CAR submission, rejection/acceptance

PROCESSING OF CAPA (Corrective and Preventive Actions)
- Root Cause Analysis (RCCA) and CAPA
- CAPA assist with historically effective RCCA
- CAPA creation and management to closure
- Audit validation of RCCA effectiveness
- CAPA system-generated assignment suggestion/selection

Users: a quality team of ~10 for the pilot, eventually thousands company-wide,
plus external suppliers who must answer CARs. Everything needs an audit trail.
```

---

## Stage 1 — Understand

> Paste this together with the requirements block above.

```text
You are helping me evaluate whether we can replace a spreadsheet-based
quality tracking process with a real application. Below are the raw
requirements as I received them.

Before proposing anything, demonstrate that you understand the domain:

1. Explain, in plain English a non-quality-engineer could follow, what
   escapes, CARs, and CAPAs are and how the three record types relate to
   each other in a real manufacturing quality process.
2. Walk through the lifecycle of a single real-world incident (invent a
   concrete example, e.g. a cracked bracket reaching a customer) as it
   would flow through all three record types.
3. Identify what the spreadsheet approach cannot enforce that an
   application could — list the specific process gates hiding in these
   requirements.
4. List the ambiguities or open questions you would ask the quality team
   before building. Then state the assumption you would proceed with for
   each if no answer were available.

Do not propose an architecture or write any code yet.
```

**What to look for:** it should independently discover the gates (a CAR
shouldn't be issuable without validation; a CAPA shouldn't close without an
effectiveness check; an escape needs containment before closure) and connect
the three record types into a chain — none of which is stated explicitly in
the requirements.

## Stage 2 — Plan

```text
Good. Now propose a plan for a working prototype I could run on my laptop
today and demo to my team this week.

- Choose a tech stack and justify it in two sentences. Optimize for: zero
  licensing cost, minimal dependencies, runnable with one command, easy for
  IT to host later. Not for resume keywords.
- Define the data model: entities, key fields, and how records link.
- Define the workflow state machines for each record type — statuses and
  which transitions are legal, including the gates you identified.
- Define the role model (quality team, read-only users, external suppliers)
  and what each role can see and do.
- For the "AI assist" requirements (response recommendation, historically
  effective RCCA assist, assignment suggestion): propose how to deliver real
  functionality WITHOUT any external AI service — using only the data the
  system itself accumulates.
- List what you are deliberately leaving out of the prototype and why.

Present the plan compactly. Do not write the application yet.
```

**What to look for:** a defensible small stack (not a 12-service Kubernetes
diagram), state machines that match the gates from Stage 1, and a similarity-
over-history answer for the "AI" features. The what-I'm-leaving-out list is
where you see engineering judgment.

## Stage 3 — Explain

```text
Before you build it: write the explanation of this application I would give
to my quality team, who are skeptical spreadsheet users, in under 300 words.
No technical vocabulary. Focus on what changes for them day to day and what
the tool refuses to let go wrong. End with the three biggest benefits over
the spreadsheet, one line each.
```

**What to look for:** whether the model can switch audiences. Same system,
zero jargon. This is the skill people don't expect AI to have.

## Stage 4 — Build

```text
Now build the prototype exactly as planned.

Requirements:
- Complete, runnable code — every file in full, no placeholders or TODOs.
- One command to install, one to run, then usable from a browser.
- Seed it with realistic demo data so it's demoable immediately.
- Enforce the workflow gates server-side, not just in the UI.
- Include automated tests for the core workflows (escape lifecycle, CAR
  validate→issue→respond→accept→close, CAPA effectiveness gate) and run
  them; show me the results.
- Include a README with run instructions.

After building, tell me: what you would add next, and what would need to
change before real production use.
```

**What to look for:** does it run first try? Do the tests pass? Click through
the UI and try to break a gate (close an escape with no containment plan,
issue an unvalidated CAR) — the app should refuse.

## Stage 5 (optional) — Iterate

Pick whichever lands best with your audience:

```text
Add an analytics page: created-vs-closed trend, average days to close,
open-record aging, and a root-cause Pareto chart. No external charting
libraries. Then show me a screenshot or describe how to verify it.
```

```text
A viewer clicked "delete" and nothing stopped them. Find out whether my
roles are actually enforced on the server, prove it either way with a test,
and fix any gaps.
```

---

## Talking points for the demo

- **The staging is the skill.** Understand → plan → explain → build is how a
  senior engineer works. The prompts just make the AI do it visibly, in order.
- **Time math.** This exercise produces in under an hour what is typically
  quoted as weeks of work. The reference implementation in this repository —
  the same scope plus login/roles, attachments, analytics, CSV import/export,
  email notifications, Docker packaging, 23 automated tests, and full
  documentation — was built in a handful of working sessions.
- **Where the human stays essential:** knowing the requirements are the real
  ones, judging the plan, choosing what "good enough" means, pilot feedback,
  and everything organizational (IT, security review, adoption). The AI
  compresses the coding column; the judgment column is still yours.
- **Compare notes.** After the exercise, open this repository and compare the
  colleague's generated prototype against `docs/ARCHITECTURE.md` — same
  requirements, independently derived designs. The convergences (state
  machines, similarity-based recommendations) and divergences are both
  instructive.
