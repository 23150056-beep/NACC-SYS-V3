# NACC SYS V3 — AI-Integrated Child Case Management & Counseling Support System

Capstone system for the National Authority for Child Care – Regional
Alternative Child Care Office I (RACCO I), **version 3**.

V3 keeps V2's clinical workflow and case management system intact and changes
how it is **deployed**: from a single office PC to a cloud environment.
Containers, managed PostgreSQL, object storage for uploaded case files, and an
AI layer that works with either an on-premises model or a hosted provider.

## What changed from V2

| | V2 (office PC) | V3 (cloud) |
|---|---|---|
| Runtime | `manage.py runserver` on Windows | Gunicorn in a container |
| Database | Local PostgreSQL | Managed PostgreSQL via `DATABASE_URL` |
| Uploads | `backend/media/` on disk | S3-compatible object storage (private bucket) |
| Static files | Served ad hoc | WhiteNoise, collected at image build |
| Config | `.env` file | Environment variables from the platform's secret store |
| AI runtime | Ollama, loopback-only | Ollama **or** a hosted API, selectable in Settings |
| Deploys | Manual copy + restart | Push to git → CI → platform deploy |
| Health | — | `/healthz/` readiness probe |

The application itself — modules, roles, permissions, copyright rules — is
unchanged from V2.

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
| AI layer | Pre-session brief, report document intelligence, remark polishing, census narrative — all optional, all drafts, all audited |

Monorepo: `backend/` (Django 5.1 + DRF + SimpleJWT, PostgreSQL) ·
`frontend/` (React 18 + Vite + Tailwind, RACCO I design system).

## Quick start

### Full stack in Docker (closest to production)

```bash
cp backend/.env.example backend/.env
docker compose up --build
```

Frontend <http://localhost:5173> · API <http://localhost:8000> ·
health <http://localhost:8000/healthz/>

### Without Docker

```bash
# backend
cd backend
python -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env              # SQLite fallback works out of the box
.venv/bin/python manage.py migrate
.venv/bin/python manage.py seed_initial_data
.venv/bin/python manage.py runserver          # http://localhost:8000

# frontend (new terminal)
cd frontend
cp .env.example .env
npm install && npm run dev                    # http://localhost:5173
```

Default admin (change the password immediately): `admin@racco1.gov.ph` / `admin1234`

Tests: `.venv/bin/python manage.py test` (backend suite, 319 tests).

## Deploying

See **[`docs/CLOUD-DEPLOYMENT.md`](docs/CLOUD-DEPLOYMENT.md)** — Render
blueprint, any-Docker-host instructions, the full environment variable
reference, backups, and the security checklist.

One-click on Render: the repo ships [`render.yaml`](render.yaml), which
declares the database, API service, and frontend.

Two things that will bite a cloud deploy if skipped:

- **Set `USE_S3=true`.** Container disks are destroyed on every deploy, so
  without object storage uploaded reports and consent scans are silently lost.
- **Set a real `DJANGO_SECRET_KEY`.** The app refuses to boot with the dev
  default when `DJANGO_DEBUG=False`.

## Sign-in

Two paths, and which one you get depends on your role:

- **Administrator** — email and password only. The admin account is the
  agency's way back in, so it is deliberately not tied to a third-party
  identity provider.
- **Psychologist / Staff** — email and password, **or** Google Sign-In.

Google Sign-In **never creates accounts**. An Administrator creates the user
first, with the correct role and the person's Google address as their email;
Google then replaces the password for that already-authorised account. An
unknown Google address is refused. Set `GOOGLE_OAUTH_CLIENT_ID` on the API to
switch it on — no frontend rebuild — and see
[the setup guide](docs/CLOUD-DEPLOYMENT.md#9-google-sign-in-optional).

## Roles

- **Administrator** — users, settings, catalog governance, AI feature flags, all reports.
- **Psychologist** — assigned children only: pre-assessment flow, instruments
  catalog (own), agency form templates (with attestation), remarks, treatment
  plans, result entries, report uploads, own availability/appointments,
  terminate own cases with reason.
- **Staff** — child/guardian records, read-only monitoring & summaries,
  booking appointments against psychologist availability.

There is no child-facing UI.

## AI (optional)

Every AI output is a **draft** the psychologist confirms; every call is audited
in `tbl_ai_job`; the system is fully functional with AI off. Care-gap alerts are
deterministic and never involve a model.

An administrator picks the runtime in **Settings → AI Assistance**:

- **On-premises (Ollama)** — install [Ollama](https://ollama.com),
  `ollama pull qwen2.5:7b-instruct`, enable the master switch. The endpoint is
  restricted to loopback, so case data never leaves the machine.
- **Hosted API (cloud)** — for deployments with no GPU host. Set
  `AI_HOSTED_API_KEY` in the server environment and choose the model in
  Settings. The key is never stored in the database and never returned by the
  API.

The hosted provider sends case text off-server for processing, which changes
the Data Privacy Act posture — read
[the data-residency section](docs/CLOUD-DEPLOYMENT.md#6-data-residency-and-ra-10173)
before enabling it on real data.

## Docs

- `docs/CLOUD-DEPLOYMENT.md` — **cloud setup**, env reference, backups, security checklist & role matrix
- `docs/DEPLOYMENT.md` — on-premises single-PC setup (still supported)
- `docs/v2-planning/` — rebuild plan, psychologist interview notes, athenaOne research
- `docs/superpowers/` — v1 design/plan history (carried for provenance)
