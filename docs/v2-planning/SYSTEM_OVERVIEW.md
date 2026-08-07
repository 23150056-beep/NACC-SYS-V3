# NACC SYS — Current System Breakdown

**AI-Integrated Child Behavioral Assessment and Counseling Support System for NACC–RACCO I**
(Regional Alternative Child Care Office I, Bauang, La Union)

Snapshot as of `main` @ `adaaba8` (2026-07-04). This documents what actually exists in code today, not the roadmap.

---

## 1. Architecture

| Layer | Stack |
|---|---|
| Frontend | React 18 + Vite + React Router 6, Tailwind CSS, `recharts` (charts), `lucide-react` (icons), `axios` |
| Backend | Django 5.1 + Django REST Framework, `djangorestframework-simplejwt` (JWT auth), `django-cors-headers` |
| Database | SQLite (dev). Designed to move to PostgreSQL later; not yet done |
| OCR / extraction | PyMuPDF (`fitz`) + `pytesseract`/Pillow (optional, only for scanned/photo instrument uploads) |
| AI / analysis | **No LLM.** 100% free, deterministic rule-based scoring engine (see §5) |

Monorepo layout: `backend/` (4 Django apps: `accounts`, `children`, `assessments`, `activity`) + `frontend/` (React SPA) + `docs/` (specs & plans).

Test coverage: **129 backend tests, all passing** across the 4 apps.

---

## 2. Roles & Access Model

Three login roles (a 4th, "Child Respondent," is a kiosk-mode UI, not an account):

| Role | Can do |
|---|---|
| **Administrator** | Full access everywhere: users, all children/records (no assignment scoping), all instruments, all assessments, settings, both report views |
| **Psychologist** | Isolated to **their own assigned children**; owns and manages their own assessment instruments; is the only role that can take/administer an assessment; can view/edit progress notes & goals for assigned children |
| **Staff** | Read access to records, results, monitoring, and the agency summary; cannot take assessments or manage instruments; can create/edit/archive child & guardian records |
| **Child Respondent** | Not a login — a full-screen, emoji-driven survey UI handed to a child mid-assessment by the psychologist (kiosk mode) |

Enforcement lives in DRF permission classes (`accounts/permissions.py`, `children/permissions.py`): `RecordsAccess`, `CanManageInstruments`, `CanTakeAssessments`, `CanViewResults`, `ProgressRecordAccess`. Psychologists are scoped server-side (queryset filtering), not just hidden in the UI.

---

## 3. Backend: Data Model

### `accounts` app
- **Role** — `Administrator` / `Psychologist` / `Staff`
- **User** — custom `AbstractUser`, email-based login, `role` FK, `active`/`archived` status

### `children` app
- **Guardian** — legacy contact record (deprecated in favor of psychologist assignment, kept for migration safety)
- **Child** — the case record: name, birth date, gender, structured location (Province → Municipality/City → Barangay), `case_type` (Foster Care, Kinship Care, Residential Care, Family Tracing & Reunification, Independent Living — Adoption intentionally excluded), `surrendered_by` (Social Worker / Police / Relatives), `assigned_psychologist`, `assignee_sees_history` flag (controls whether a reassigned psychologist inherits prior history), active/archived status
- **ProgressNote** — dated free-text session/progress note tied to a child + author
- **Goal** — a treatment goal on a child's record: text, `ongoing`/`met` status, target date, author

### `assessments` app
- **Questionnaire** — an assessment instrument: title, age group, description, draft/active/archived status, **owner** (one psychologist per instrument, admin assigns/reassigns)
- **Question** — belongs to a questionnaire; type (`rating_scale`, `yes_no`, `multiple_choice`, `emotion`, etc.), options, order, plus scoring metadata (`concern_direction`: higher/lower, `concern_options`)
- **Assessment** — one administration of a questionnaire to a child: psychologist, questionnaire, date, practitioner `notes` + manual `classification`, `respondent_mode` (staff vs child/kiosk), `next_session` date, `is_locked`/`locked_at` (finalize-and-freeze)
- **Response** — one answer to one question within an assessment
- **AssessmentResult** — engine output: `behavioral_score` (0–100), `classification`, `confidence`, `overridden` flag
- **Recommendation** — generated guidance text + priority level, linked to a result
- **AnalysisSetting** — singleton config: minimum confidence threshold, whether low-confidence results require a mandatory practitioner override

### `activity` app
- **ActivityLog** — append-only audit/notification feed: actor, optional `recipient` (targets a notification at one user, e.g. a newly-assigned psychologist), action (created/updated/archived/login), category (record/user/security), entity reference

---

## 4. Backend: API Surface (`/api/...`)

| Area | Endpoints |
|---|---|
| Auth | `POST auth/login/`, `POST auth/refresh/`, `GET auth/me/` (JWT) |
| Roles/Users | `roles/`, `psychologists/` (list, for assignment dropdowns), `users/` (Admin-only CRUD) |
| Records | `children/`, `guardians/` (CRUD + `/archive/` soft-delete), `progress-notes/`, `goals/` |
| Instruments | `questionnaires/` (nested questions, `/publish/`, `/archive/`, `POST questionnaires/extract/` — OCR/PDF → draft), `active-questionnaires/` |
| Assessments | `assessments/` (CRUD, `POST assessments/analyze/` preview-only scoring, `PATCH .../` edit-with-audit, `POST .../finalize/` lock) |
| Settings | `analysis-settings/` (Admin-only write) |
| Reporting | `reports/child/<id>/` (per-child trajectory), `reports/summary/` (agency-wide, `?export=csv`), `reports/dashboard/` (live stat cards/trends), `reports/monitoring/` (cross-child monitoring list) |
| Activity | `activity/` (read-only, `?category=` filter, capped at 50) |

---

## 5. The Analysis Engine (rule-based, no LLM, no external calls)

`assessments/analysis/scoring.py` + `recommendations.py`:

1. Each answer maps to a **concern value 0–1** based on the question's type and its configured `concern_direction`/`concern_options` (e.g. a 5-point rating scale where "5" is concerning vs. one where "1" is).
2. Concern values average into a **behavioral_score (0–100)**.
3. Score buckets into three classifications:
   - **< 34 → Normal**
   - **34–66 → Needs Monitoring**
   - **≥ 67 → Needs Counseling Attention**
4. A separate **confidence score (0–100)** blends *coverage* (how many questions were answered/scorable) and *decisiveness* (how far the score sits from a boundary).
5. Low-confidence results can be gated behind a **mandatory practitioner override** (configurable threshold in Settings, default 80%).
6. **Recommendations** are template-generated per classification (Low/Medium/High priority), naming the top concerning items, with a fixed disclaimer that this is decision support, not a diagnosis.
7. The engine's automated classification is always kept **separate** from the practitioner's own manual classification/notes — both are stored and shown side by side.
8. `get_recommender()` is a deliberate swap-seam for plugging in an LLM later without touching callers; today it's 100% deterministic and free.

### Instrument digitization (OCR)
`assessments/extraction/`: uploads (PDF/PNG/JPG) go through PyMuPDF text extraction, falling back to Tesseract OCR for scanned pages/images, then a heuristic parser guesses a title + numbered questions + likely question type (yes/no vs. rating scale). Produces an editable draft questionnaire — never auto-publishes. Pluggable `InstrumentExtractor` interface for a future smarter/LLM-based extractor.

---

## 6. Frontend: Pages & Features

| Route | Page | Who sees it | What it does |
|---|---|---|---|
| `/login` | Login | everyone | Username/email + password, forgot/reset password flow |
| `/` | Dashboard | Admin, Psych, Staff | Quick Actions on top; live stat cards keyed to engine classifications (Needs Counseling Attention / Needs Monitoring / Normal / Total / Unassessed); weekly/monthly trend chart; case-type mix; Case Types by Psychologist; role-scoped activity feed |
| `/children` | Records | Admin, Staff, Psych (read) | Child + guardian roster: assign psychologist, case type, surrendered-by, cascading Province/City/Barangay pickers, archive, A–Z sort, age-group grouping (Child 1–12 / Teen 13–17) |
| `/questionnaires` | Assessment Instruments | Admin, Psychologist | Build/edit questionnaires by hand, or upload a paper instrument (PDF/photo) to OCR into a draft, publish/archive, per-question concern-scoring config |
| `/assessment` | Assessment (wizard) | Psychologist only | Pick assigned child + owned instrument → answer/administer → optional **"Hand to child"** kiosk mode (`RespondentSurvey.jsx`: big emoji faces, 👍/👎, one question per screen, progress dots) → engine analysis preview → practitioner notes/classification → sign |
| `/monitoring` | Progress Monitoring | Admin, Staff, Psych | Cross-child table: trajectory (Improving/Worsening/Stable/Baseline) derived from score history, search + trajectory filter, links into each child's progress report |
| `/report` | Assessment Results | Admin, Staff, Psych | List of completed assessments with outcome badge + score; drawer shows engine analysis next to practitioner classification/notes |
| `/report/child/:id` | Child Progress Report | everyone (scoped) | Full trajectory for one child: recharts trend line, assessment history, inline **edit notes/classification with audit trail**, **finalize/lock**, **Progress Log** (dated notes) and **Treatment Goals** sections, "Schedule next session" action |
| `/reports/summary` | Agency Summary | Admin, Staff | Weekly/monthly/yearly KPIs, per-psychologist caseload breakdown, attention list, **Print** and **CSV export** |
| `/users` | User Management | Admin only | CRUD on staff/psychologist/admin accounts, role assignment (locked once set), username derived from email |
| `/settings` | Settings | Admin only | Agency config placeholder, AI-engine confidence threshold slider, override toggle (writes to `AnalysisSetting`) |

### Cross-cutting UI pieces
- **Sidebar** — role-filtered nav grouped into Overview / Casework / Clinical / Governance sections
- **Topbar** — notification bell (activity feed, tabbed by category), top-level Log Out
- **RACCO I Workspace design system** (`src/ui/index.jsx`, `src/index.css`) — shared tokens + primitives (Card, Badge, SeverityBadge, ConfidenceMeter, ProgressSteps, Alert, EmptyState, Switch, RoleBadge, etc.), Baloo 2 / Nunito Sans / IBM Plex Mono type
- **ActivityContext / ToastContext / AuthContext** — global providers for notifications, toasts, and JWT session state

---

## 7. Known Placeholders / Not-Yet-Real

- `frontend/src/config/caseData.js` — case types, "surrendered by" options, and Province/Municipality/Barangay lists are **placeholder values** pending the partner agency's business-process interview.
- Settings page's "RCPC" name and "NACC API Endpoint / sync" fields are **UI placeholders only** — no real national-office integration exists.
- No PostgreSQL migration yet (still SQLite, gitignored `db.sqlite3`).
- No production deployment/hosting configured.

## 8. Explicitly Out of Scope (by design)

- No LLM/external AI call anywhere — the analysis engine is intentionally deterministic and free, with a swap-seam (`get_recommender()`) left for later.
- No "Compliance & Audit" page (removed in the 2026-06-30 access rework; superseded by the `activity` log + per-record audit trail on edits/finalization).
