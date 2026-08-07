# NACC SYS V2 — Full Rebuild & Structure Plan

**AI-Integrated Child Case Management and Counseling Support System for NACC–RACCO I**
Plan date: 2026-07-04 · Basis: v1 codebase @ `adaaba8`, psychologist interview (Ma'am Hannah), athenaOne structure research.

Decisions locked: **keep Django 5.1 + React 18/Vite stack · copy v1 and refactor · local/free LLM (Ollama) for AI**.

---

## 1. Why V2 Exists

1. **Copyright blocker (primary driver).** Standardized psychological assessment instruments (their items, scales, scoring keys) are copyrighted by their publishers. v1's core loop — digitize an instrument (manually or via OCR upload), administer it in-app, score it — reproduces instrument content inside the system. The partner psychologist confirmed this cannot be implemented. Everything downstream of that loop (kiosk mode, rule-based scoring engine, auto-classification) loses its data source and must go.
2. **Workflow mismatch.** The psychologist administers instruments on paper, in person, using her own materials. The system's real job is what happens *around* testing: scheduling, consent, intake interview, tracking which instruments were used, capturing her findings, storing her reports, and monitoring the caseload.
3. **Modernization target.** Rebuild the module structure on the athenaOne pattern (Clinicals / Collector / Communicator + AI layer) so V2 has a defensible architecture story and a clear place for AI.

### V2 in one sentence
V2 pivots from an *instrument administration and auto-scoring system* to a *clinical workflow and case management system*: the psychologist's own documents and inputs are the data, instruments exist only as catalog titles, and a local LLM assists with summarization and document intelligence.

---

## 2. Copyright Compliance Policy (design rule for every feature)

**Never stored in the system:** instrument questions/items, answer options, scales, scoring keys, norms tables, or scanned/uploaded copies of published instruments. No OCR of instruments. No in-app administration of published instruments.

**Safe to store (and why):**

| Content | Why it's safe |
|---|---|
| Instrument **titles + metadata** (publisher, age range, category) | Titles and bibliographic facts are not copyrightable |
| **Consent forms** authored by the agency/psychologist | Agency-authored original work |
| **Clinical Interview Form** authored by the psychologist | Author's own work |
| "Problems encountered" checklists written by the psychologist | Author's own work |
| NACC **Self-Report Questionnaire** and similar NACC/DSWD forms | Philippine government works — no copyright under RA 8293 §176 |
| SAMD Certification Assessment Tool (KRAs) | Philippine government work |
| The psychologist's **own reports, remarks, results summaries** | Her own professional work product |

**Enforcement in-product:** the (repurposed) form builder is restricted to agency forms and requires an attestation checkbox — "This form is agency-authored or an official government form, not a published assessment instrument." Document uploads are typed (Psychological Report / Consent / Interview / Other-agency-doc); there is no "instrument" upload type anywhere.

---

## 3. Architecture

| Layer | V2 stack | Change from v1 |
|---|---|---|
| Frontend | React 18 + Vite + Router 6, Tailwind, recharts, lucide, axios | Kept. Add a calendar component (`react-big-calendar` or FullCalendar) |
| Backend | Django 5.1 + DRF + SimpleJWT + CORS | Kept |
| Database | **PostgreSQL** (do the migration at the start of V2, not later) | SQLite → Postgres |
| File storage | Local media volume for uploaded PDFs/DOCX (reports, signed consents); UUID filenames, private serving via authenticated endpoint | New |
| Text extraction | PyMuPDF (already in v1) — reused, but now pointed at the psychologist's **own** uploaded reports, never instruments | Repurposed |
| AI | **Ollama** running locally (same machine or office server), REST at `localhost:11434`; recommended model **Qwen 2.5 7B** or **Llama 3.1 8B** (Q4 quant, runs on a 16 GB-RAM office PC; usable on 8 GB) | New `ai` Django app |
| OCR (pytesseract) | **Removed** | Deleted with instrument extraction |

Monorepo layout (copied from v1, then refactored):

```
backend/
  accounts/        # kept as-is (roles, JWT, permissions)
  children/        # expanded: profiling, statuses, termination
  clinical/        # REPLACES assessments/: catalog, pre-assessment,
                   # forms, documents, remarks, treatment plans, results
  scheduling/      # NEW: appointments, availability, calendar feeds
  activity/        # kept as-is (audit/notification feed)
  ai/              # NEW: Ollama client, prompt templates, feature flags
  config/
frontend/
  src/pages, src/ui (RACCO I design system kept), src/context
docs/
```

---

## 4. athenaOne → NACC SYS V2 Module Map

| athenaOne | What it does there | NACC V2 analog |
|---|---|---|
| **athenaClinicals** (EHR, guided encounter documentation) | Chief complaint → exam → assessment → plan | **Clinical Workspace**: child chart + guided pre-assessment flow (consent → clinical interview → instrument selection → session → results entry → report upload) |
| **athenaCollector** (practice mgmt / RCM) | Billing, claims, operations | No billing here → **Case Operations & Governance**: caseload census, termination/archival control, audit trail, agency summary, optional SAMD certification-readiness checklist |
| **athenaCommunicator** (patient engagement, scheduling) | Portal, reminders, online scheduling | **Scheduling module**: psychologist availability, appointment calendar, session statuses, follow-up alerts. (Guardian-facing portal deliberately excluded — child-protection scope, RA 11642; listed as future work only) |
| **Insights Dashboard / benchmarking** | KPIs vs network | **Census Dashboard**: active/inactive counts, case-type mix, per-psychologist caseload, monthly intake/discharge trends |
| **AI layer** (Ambient Notes, chart summarization, Sage copilot, Document Services AI) | Drafts notes, summarizes charts, extracts data from faxes | **Local AI layer**: pre-session brief, document intelligence on own reports, remark-note polishing, deterministic care-gap alerts (see §8) |

athenahealth's 2026 direction validates the AI picks: chart summarization before every exam, document intelligence extracting data from incoming documents, and an embedded copilot are their flagship features — V2 mirrors all three at clinic scale with a local model.

---

## 5. Roles & Access (small deltas from v1)

| Role | V2 changes |
|---|---|
| **Administrator** | Unchanged: full access, user management, settings, all reports. Gains: instrument catalog governance (approve titles), AI feature flags |
| **Psychologist** | Still scoped to assigned children. Now: manages own instrument catalog entries, consent/interview form templates, runs pre-assessment flow, uploads reports, writes remarks/treatment plans, enters results manually, manages own schedule/availability, terminates (archives) own cases with reason |
| **Staff** | Unchanged: create/edit child & guardian records, read-only monitoring and summaries. Gains: can book appointments against psychologist availability |
| **Child Respondent (kiosk)** | **Removed entirely** — no in-app administration means no child-facing UI |

Permission classes from v1 (`RecordsAccess`, `CanManageInstruments`, etc.) are kept and renamed where needed; queryset scoping stays server-side.

---

## 6. Data Model — Delete / Keep / Add

### Deleted from v1
`Question`, `Response`, `AssessmentResult` (engine output), `Recommendation`, `AnalysisSetting`, the whole `assessments/analysis/` scoring engine, and `assessments/extraction/` (OCR). `Questionnaire` survives only in mutated form (below).

### Kept as-is
`Role`, `User`, `Guardian`, `ActivityLog`.

### Changed
**`Child`** — expanded profile:
- keep: name, birth date, gender, Province/Municipality/Barangay, `assigned_psychologist`, `assignee_sees_history`
- `case_type`: now **includes Adoption** (interview: "active/adoption, active/foster care") alongside Foster Care, Kinship Care, Residential Care, FTR, Independent Living — final list to be confirmed with RACCO I
- `status`: `active` / `inactive` (inactive = terminated/archived)
- new profiling fields: photo (optional), referral source, referral reason, education level, current placement, medical notes — confirm exact field list with the psychologist
- computed: `pre_assessment_status` ("Answered" / "Not yet") and the list of instrument titles used — both surfaced on the profile

### New models

| App | Model | Fields (core) |
|---|---|---|
| clinical | **InstrumentCatalog** | title, publisher, category (cognitive/behavioral/projective/…), age_range, notes, owner (psychologist), active. **Metadata only — no items, ever** |
| clinical | **AgencyFormTemplate** | type (`consent` / `clinical_interview` / `problem_checklist` / `self_report_gov`), title, versioned field definitions (JSON), owner, attestation flag + timestamp. This is v1's questionnaire builder repurposed for agency-authored forms only |
| clinical | **PreAssessment** | child, psychologist, date, status (`pending`/`in_progress`/`completed`), instruments (M2M → InstrumentCatalog), linked consent record, linked clinical interview record, notes |
| clinical | **ConsentRecord** | pre_assessment/child, template used, signer name + relationship to child, date, uploaded scan of signed form (optional), status |
| clinical | **ClinicalInterviewRecord** | child, template used, answers (JSON), interviewer, date |
| clinical | **ProblemEntry** | child, description, category, identified_on, resolved flag ("list of problems encountered in the child") |
| clinical | **PsychologicalReport** | child, author, file (PDF/DOCX), report_type, session/date coverage, extracted_text (PyMuPDF), `ai_summary` (nullable, human-confirmed flag) |
| clinical | **RemarkNote** | child, author, date, text (replaces v1 session notes; "psychological remark notes, manually added") |
| clinical | **TreatmentPlan** | child, author, objectives text, interventions text, status, review date |
| clinical | **ResultEntry** | child, pre_assessment, instrument (FK → catalog title), summary/findings text, classification text (free, psychologist's own words), date. **Manual input only — no computed scores** |
| clinical | **TerminationRecord** | child, terminated_by, date, reason category + required note; sets child → inactive |
| scheduling | **AvailabilityBlock** | psychologist, weekday/date, start–end, capacity |
| scheduling | **Appointment** | child, psychologist, datetime, purpose (`pre_assessment`/`session`/`follow_up`), status (`scheduled`/`completed`/`no_show`/`cancelled`), linked pre_assessment |
| ai | **AIJob** | type, input refs, output text, model used, latency, accepted/rejected by user (audit of every AI call) |
| ai | **AISetting** | feature flags per AI capability, Ollama URL, model name, on/off master switch |

---

## 7. Frontend — Pages & Features (V2 spec)

| Route | Page | Who | V2 behavior |
|---|---|---|---|
| `/login` | Login | all | Unchanged from v1 |
| `/` | **Census Dashboard** | Admin, Psych, Staff | Rebuilt on the athena dashboard pattern. **Removed:** Needs Counseling / Needs Monitoring / Normal stat cards, assessment-over-time chart. **New:** summary census (active/inactive overall + per case type incl. adoption/foster care), today's schedule strip with clickable appointment tiles (child name, age, time, purpose, status — athena scheduling-tile pattern), psychologist availability at a glance, monthly intake vs. termination trend, pending pre-assessments count, care-gap alert list, role-scoped activity feed |
| `/children` | Records | Admin, Staff, Psych | Roster + expanded **child profiling**. Status chips: `Active · Adoption`, `Active · Foster Care`, `Inactive (Terminated)`. Shows pre-assessment status ("Answered" / "Not yet") and instrument titles used. Tabs within a child: Profile · Pre-Assessments · Progress · Documents · Schedule |
| `/instruments` | **Pre-Assessment Instruments** | Psych (own), Admin (all) | Title-only catalog list (add/edit/deactivate metadata). Consent form templates + Clinical Interview form templates managed here (agency-forms builder w/ attestation). No questions, no OCR, no publish flow |
| `/pre-assessment` | **Pre-Assessment (guided flow)** | Psych only | Replaces v1 assessment wizard. Steps: pick child → verify/collect **consent** → **clinical interview form** → select instrument **titles** to administer (paper, offline) → log problems encountered → mark completed → optional: schedule next session. Mirrors athenaClinicals' guided encounter documentation |
| `/monitoring` | Progress Monitoring | Admin, Staff, Psych | Per interview: **removed** assessment timeline, treatment-goal tracker, session notes. **Now shows** per child: pre-assessment history with instrument titles used, uploaded psychological reports, psychological remark notes, treatment plan, and the **archive/terminate action** (requires reason note). Cross-child table keeps search/filter but trajectory column becomes "last activity / next appointment / flags" (no engine scores exist) |
| `/report/child/:id` | Child Report | scoped | Chart view of one child: profile header, pre-assessment log, result entries (manual), report file list w/ preview/download, remarks log, treatment plan, AI pre-session brief button |
| `/reports` | Reports & Uploads | Admin, Staff, Psych | List of result entries + uploaded reports across caseload; **upload report** (each psychologist keeps her own format — file upload, not a forced template); CSV export; print |
| `/reports/summary` | Agency Summary | Admin, Staff | Census KPIs (weekly/monthly/yearly), per-psychologist caseload, terminations by reason, pending consents/pre-assessments; print + CSV kept from v1 |
| `/schedule` | **Calendar** | Admin, Psych, Staff | NEW. Month/week calendar of appointments; psychologist sets availability blocks; staff/admin book against availability; statuses (completed/no-show/cancelled); feeds the dashboard tiles |
| `/users`, `/settings` | Admin | Admin | v1 user CRUD kept. Settings: drop analysis-engine threshold slider; add AI feature flags (master switch, per-feature), Ollama endpoint/model, storage limits |

Kept cross-cutting pieces: sidebar (regrouped: Overview / Casework / Clinical / Schedule / Governance), topbar notification bell, RACCO I design system, Auth/Toast/Activity contexts.

---

## 8. AI Integration (local, free, private — Ollama)

**Runtime:** Ollama on the office PC/server; Django `ai` app calls `http://localhost:11434/api/generate|chat`. Recommended: **Qwen 2.5 7B instruct** (best small-model quality for structured extraction) or **Llama 3.1 8B**, Q4 quantization — both run on a 16 GB-RAM machine with no GPU (≈6–9 tok/s on low-end CPUs, fine for on-demand summaries). All child data stays on-premises → strong RA 10173 (Data Privacy Act) story for the capstone defense.

**Design rules:** every AI feature is behind a flag and the system is fully functional with AI off; every output is a *draft* the psychologist confirms/edits (human-in-the-loop); every call is logged to `AIJob`; a fixed disclaimer marks output as decision support, not diagnosis; prompts send the minimum necessary fields (no full identity dump).

| # | Feature | athena analog | How it works |
|---|---|---|---|
| A1 | **Pre-Session Brief** | Chart summarization ("enter every exam prepared") | Button on child chart / appointment tile → compiles recent remarks, last pre-assessment, latest report summary, open problems → LLM produces a 150-word brief |
| A2 | **Report Document Intelligence** | Document Services AI | On upload of the psychologist's own PDF report: PyMuPDF extracts text → LLM drafts structured fields (key findings, recommendations, classification-in-her-words) → psychologist confirms before it lands on the profile |
| A3 | **Remark Polishing** | Ambient Notes (lite) | Psychologist types shorthand remark → LLM rewrites into clean clinical prose → she edits/accepts |
| A4 | **Care-Gap Alerts** | Care gap detection | **Deterministic, no LLM** (free, reliable): overdue follow-up (> N days since last session), consent missing before pre-assessment, pre-assessment "Not yet" > X days after intake, no report uploaded after completed pre-assessment, active child with no upcoming appointment |
| A5 | **Census Insights** | Insights Dashboard | Deterministic aggregates (case-type mix, intake/termination trends, per-psychologist load); optional LLM-written monthly narrative summary for the agency report |

Build order within AI: A4 (deterministic, ship first) → A1 → A2 → A3 → A5 narrative. v1's `get_recommender()` swap-seam philosophy carries over: `ai/services.py` exposes `get_ai_client()` returning either the Ollama client or a `NullClient`.

---

## 9. Explicitly Deleted from v1 (and why)

| Removed | Reason |
|---|---|
| Questionnaire builder with items/options | Reproduces copyrighted instrument content |
| OCR instrument upload (`extraction/`, pytesseract) | Digitizing published instruments = infringement vector |
| In-app administration + kiosk mode (`RespondentSurvey.jsx`) | No instrument items in system → nothing to administer |
| Rule-based scoring engine, `behavioral_score`, auto-classification, confidence, `AnalysisSetting` | No response data to score; psychologist enters results manually |
| Auto-generated `Recommendation` | Replaced by psychologist's own treatment plan + AI-drafted, human-confirmed summaries |
| Dashboard classification stat cards + assessment-over-time chart | Interview explicitly asked for census/schedule dashboard instead |
| Treatment *goals* tracker & session notes (as v1 modeled them) | Interview: replaced by uploadable reports and remark notes; treatment plan becomes psychologist free-input |

---

## 10. Refactor Path (copy v1 → V2), in build order

Each step leaves the app runnable; adapt v1's test suite as you go (delete engine/extraction/kiosk tests, keep the ~90 auth/records/activity tests).

1. **Bootstrap** — copy v1 into `NACC-V2/`, fresh git repo, switch to PostgreSQL, wire media file storage, update `.env.example`.
2. **Prune** — delete `assessments/analysis/`, `assessments/extraction/`, kiosk components, analyze/finalize endpoints tied to scoring, classification dashboard cards. Get the reduced app green.
3. **Children expansion** — profiling fields, `status` + adoption case type, `TerminationRecord` + archive-with-reason flow. Confirm real case-type / location / referral lists with RACCO I (kills v1's placeholder `caseData.js`).
4. **Clinical app** — rename/rework `assessments` → `clinical`: `InstrumentCatalog` (strip questions from old Questionnaire), `AgencyFormTemplate` + attestation, consent + clinical-interview records, `ProblemEntry`.
5. **Pre-assessment flow** — guided wizard (consent → interview → titles → problems → complete), profile surfacing of "Answered / Not yet" + titles used.
6. **Documents & findings** — `PsychologicalReport` upload (+ PyMuPDF text extraction), `RemarkNote`, `TreatmentPlan`, `ResultEntry`; rebuild Progress Monitoring page per interview.
7. **Scheduling** — `scheduling` app, availability blocks, appointments, calendar UI, dashboard tiles.
8. **Dashboard & reports** — census dashboard, agency summary rework, CSV/print, care-gap alert engine (A4, deterministic).
9. **AI app** — Ollama client + flags + `AIJob` audit; ship A1 pre-session brief, then A2 document intelligence, then A3/A5.
10. **Hardening** — permissions audit vs role matrix, file-access security (authenticated media), backup/restore doc, deployment notes for the office PC.

Suggested milestones: steps 1–3 = M1 "safe core", 4–6 = M2 "clinical workflow" (this is the demo-able heart of V2), 7–8 = M3 "operations", 9–10 = M4 "AI + polish".

---

## 11. Interview Requirement → V2 Feature Traceability

| Interview item | V2 answer |
|---|---|
| Cannot implement/upload assessment tools | §2 policy; instruments = titles only (`InstrumentCatalog`); OCR deleted |
| Pre-assessment features instead | `/pre-assessment` guided flow + `PreAssessment` model (§6–7) |
| Dashboard: census, availability via schedule, calendar, active/inactive counts; remove classification cards & assessment-over-time | Census Dashboard spec (§7) |
| athenahealth dashboard idea | Appointment tiles + census + alerts, athena mapping (§4) |
| Records: profiling; active/adoption, active/foster care, inactive (terminated) | Child model expansion + status chips (§6–7) |
| See pre-assessment answered / not yet + instrument titles used on child | Computed profile fields (§6) |
| Progress monitoring based on psychologist input | `RemarkNote`, `TreatmentPlan`, manual `ResultEntry` |
| Instrument page = titles list only, linked to child profile | `/instruments` catalog (§7) |
| Consent form feature added by psychologist | `AgencyFormTemplate(consent)` + `ConsentRecord` |
| Clinical Interview form added by psychologist | `AgencyFormTemplate(clinical_interview)` + record |
| List of problems encountered in the child | `ProblemEntry` |
| Remove assessment timeline → pre-assessment tool details | Monitoring page rework (§7) |
| Remove treatment goals → uploadable psychological report | `PsychologicalReport` upload |
| Remove session notes → manual psychological remark notes | `RemarkNote` |
| Archive/termination with reason note after assessing | `TerminationRecord` flow |
| Uploadable report, each psychologist's own format | File upload, no forced template (§7 Reports) |
| Schedule assigned | `scheduling` app + calendar (§7) |

**Optional differentiator (Phase 5 / future work):** SAMD Certification-Readiness module — self-scoring checklist built from the government SAMD KRA tool already in this folder; copyright-safe and unique for a capstone. Guardian portal stays future-work-only.

---

## 12. Risks & Open Items

1. **Confirm with the psychologist** before coding: exact profiling fields, final case-type list (Adoption now included?), termination reason categories, consent form content.
2. **Office hardware** for Ollama — verify RAM (16 GB ideal); if only 8 GB, run Qwen 2.5 7B Q4 alone or fall back to deterministic-only mode (system still fully works).
3. **Data migration** — v1 children/users/activity migrate cleanly; v1 assessments/scores should be archived (exported to CSV) rather than migrated, since their engine fields have no V2 home.
4. **Capstone title** — "AI-Integrated" is still earned via A1–A5, but the paper's methodology section must be updated: AI now assists documentation and monitoring, it no longer scores children. That is also the ethically stronger position.

