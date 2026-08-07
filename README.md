# NACC SYS V2 — AI-Integrated Child Case Management & Counseling Support System

Capstone system for the National Authority for Child Care – Regional
Alternative Child Care Office I (RACCO I), **version 2**.

V2 pivots from an instrument-administration/auto-scoring system to a
**clinical workflow and case management system**: the psychologist's own
documents and inputs are the data, published assessment instruments exist in
the system only as **catalog titles**, and a **local LLM (Ollama)** assists
with summarization and document intelligence.

## Copyright compliance (design rule)

Never stored: instrument questions/items, scales, scoring keys, norms, or
scans of published instruments. No OCR of instruments, no in-app
administration, no computed scores. Instruments are administered **on paper**
with the psychologist's own materials; the system records titles, consents,
interviews, problems, manual result entries, and uploaded reports.

## Modules (athenaOne-inspired)

| Module | What it does |
|---|---|
| Clinical Workspace | Child chart + guided pre-assessment flow (consent → clinical interview → instrument titles → problems → complete), remarks, treatment plans, manual result entries, report uploads (PDF/DOCX, text-extracted) |
| Case Operations | Census, terminate-with-reason (archive), audit trail/activity feed, agency summary with CSV/print |
| Scheduling | Psychologist availability blocks, appointment booking with capacity checks, month/week calendar, statuses |
| Census Dashboard | Active/inactive per case type, today's schedule strip, intake vs termination trend, pending pre-assessments, deterministic care-gap alerts |
| Local AI layer | Pre-session brief, report document intelligence, remark polishing, census narrative — all optional, all drafts, all on-premises via Ollama |

Monorepo: `backend/` (Django 5.1 + DRF + SimpleJWT, PostgreSQL) ·
`frontend/` (React 18 + Vite + Tailwind, RACCO I design system).

## Quick start (development)

```bash
# backend
cd backend
python -m venv venv
./venv/Scripts/pip install -r requirements.txt
cp .env.example .env          # SQLite fallback works out of the box;
                              # set DB_ENGINE=postgres + DB_PASSWORD for PostgreSQL
./venv/Scripts/python manage.py migrate
./venv/Scripts/python manage.py seed_initial_data
./venv/Scripts/python manage.py runserver      # http://localhost:8000

# frontend (new terminal)
cd frontend
npm install
npm run dev                                    # http://localhost:5173
```

Default admin (change the password immediately): `admin@racco1.gov.ph` / `admin1234`

Tests: `./venv/Scripts/python manage.py test` (backend suite).

## Roles

- **Administrator** — users, settings, catalog governance, AI feature flags, all reports.
- **Psychologist** — assigned children only: pre-assessment flow, instruments
  catalog (own), agency form templates (with attestation), remarks, treatment
  plans, result entries, report uploads, own availability/appointments,
  terminate own cases with reason.
- **Staff** — child/guardian records, read-only monitoring & summaries,
  booking appointments against psychologist availability.

There is no child-facing UI in V2.

## AI (optional, local, private)

Install [Ollama](https://ollama.com), `ollama pull qwen2.5:7b-instruct`, then
enable the master switch in Settings. Every AI output is a **draft** the
psychologist confirms; every call is audited in `tbl_ai_job`; the system is
fully functional with AI off. Care-gap alerts are deterministic (no LLM).

## Docs

- `docs/DEPLOYMENT.md` — office-PC setup, backups/restore, security checklist & role matrix
- `docs/v2-planning/` — V2 rebuild plan, psychologist interview notes, athenaOne research
- `docs/superpowers/` — v1 design/plan history (carried for provenance)
