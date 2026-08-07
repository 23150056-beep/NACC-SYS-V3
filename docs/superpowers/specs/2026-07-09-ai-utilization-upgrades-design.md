# AI Utilization Upgrades — Design

**Date:** 2026-07-09
**Status:** Approved (user selected all four features)
**Context:** The local AI layer (Ollama, `qwen2.5:3b-instruct`) is now live and verified
end-to-end on the office machine. Observed: pre-session brief ≈25 s, remark polish ≈8 s,
and three quality issues — the model guessed the child's age (not a prompt input),
drifted between pronouns, and emitted curly-quote punctuation that can render as
mojibake. These upgrades make the existing AI measurably more useful without adding
infrastructure, models, or any scoring/classification of children.

**Invariants (unchanged):** every feature stays behind its `AISetting` flag; the system
is fully functional with AI off (503 degradation); every output is a draft a human
confirms; every call is audited in `AIJob`; prompts carry the minimum necessary data
(RA 10173); no copyrighted instrument content; no computed scores.

---

## F1 — Prompt hardening

Fixes the three quality issues observed live.

- **Grounding fields:** `prompts.BRIEF` gains two fields — `age` (computed from
  `Child.birth_date`; the literal string `unknown` when null) and `gender`
  (`Child.gender` or `unspecified`). Filled in by the brief prompt builder.
- **Anti-guessing instruction** appended to `BRIEF`: *"Use only the facts provided
  above. Do not state age, gender, or any other detail not given. Refer to the child
  by first name only."*
- **Punctuation normalization:** a deterministic `_normalize_output(text)` in
  `ai/services.py`, applied to every model response inside `run_job()`: curly single/
  double quotes → ASCII quotes, en/em dashes → hyphen, non-breaking space → space.
  (Post-processing beats prompting the model about punctuation — it is reliable.)

**Tests:** brief prompt contains age/gender; unknown-birthdate path; normalization
unit test with mixed Unicode punctuation.

## F2 — Pre-generated briefs

A 25 s wait is fine in the background and bad on a button press. Briefs get generated
ahead of the session and served instantly. No new queue infrastructure — a guarded
daemon thread is enough at clinic scale.

**Backend**

- Refactor the prompt assembly in `PreSessionBriefView.post` into a shared helper
  `build_brief_prompt(child)` (used by the view and the prefetcher).
- `GET /api/ai/brief/child/<id>/latest/` — newest `ok` `AIJob` with
  `job_type="brief"`, `input_ref="child:<id>"`, created **today** (local date).
  Same permissions/role-scoping as the existing brief view. Returns
  `{draft, job_id, generated_at, disclaimer}`; 404 when none.
- `POST /api/ai/prefetch-briefs/` — for the caller's **today, scheduled**
  appointments (psychologist → own children only; admin → all), finds children with
  no today-brief and generates them **sequentially in one daemon thread** (Ollama on
  CPU should never run concurrent generations). Returns
  `{queued: [child_ids], skipped: [child_ids]}` immediately.
  - Module-level in-flight set + lock prevents duplicate generation across requests.
  - Thread closes its DB connection when finished (`django.db.connection.close()`).
  - Gated by `feature_brief`; silently 503s like the other endpoints.
  - Prefetched jobs record `created_by` = requesting user.

**Frontend**

- `Schedule.jsx`: after appointments load, fire-and-forget `POST /ai/prefetch-briefs/`
  (ignore errors — degradation must be silent). The appointment detail panel for a
  today/scheduled appointment gains a **"Pre-session brief"** button: `GET …/latest/`
  first → instant modal with a "drafted <time>" stamp; on 404 fall back to the
  existing generate call with the "Working…" state.
- `ChildProgressReport.jsx`: on load, try `GET …/latest/`; when present, the existing
  AI brief button opens it instantly (stamped), with a **Regenerate** action that
  calls the existing POST.

## F3 — Case-study AI summary

`CaseStudy` already has `extracted_text` (populated on upload via `extract_pdf_text`)
plus dormant `ai_summary` / `ai_summary_confirmed` columns. This wires them up with
the exact A2 pattern.

**Backend**

- New prompt `CASE_STUDY`: from the social worker's case study text, draft
  (1) background & family/social context (3–5 bullets), (2) presenting concerns
  (2–4 bullets), (3) recommendations noted by the author (1–3 bullets). Only
  information present in the text.
- `POST /api/ai/summarize-case-study/<id>/` — mirrors `ReportSummaryDraftView`:
  gated by `feature_doc_intelligence`; 400 when no `extracted_text`; permission =
  admin/staff or the child's assigned psychologist (mirror `CaseStudyViewSet` read
  rules); saves `ai_summary`, resets `ai_summary_confirmed=False`; audit
  `job_type="case_study"` (new `TYPE_CHOICES` entry), `input_ref="casestudy:<id>"`.
- `POST /api/ai/confirm-case-study-summary/<id>/` — mirrors
  `ConfirmReportSummaryView` (admin or assigned psychologist), sets confirmed text +
  flag, marks the matching jobs' outcome (see F4).
- `CaseStudySerializer` must expose `ai_summary` + `ai_summary_confirmed` (add if
  missing).

**Frontend**

- Wherever case studies are listed with the reports split-view (`ChildProgressReport
  .jsx`, and `Report.jsx` if it renders case studies), add the same **AI summary**
  button + editable confirm modal + "confirmed / draft (unconfirmed)" label the
  psych-report files already have.

## F4 — AI usage metrics

Turns the audit trail into evaluation evidence ("psychologist accepted N% of drafts")
and a quality safeguard for the 3B model.

**Backend**

- `AIJob.outcome` — CharField choices `pending / accepted / edited / discarded`,
  default `pending` (migration). Keep the legacy `accepted` boolean in sync
  (`accepted`/`edited` → True, `discarded` → False) so nothing existing breaks.
- `POST /api/ai/jobs/<id>/feedback/` `{"outcome": "accepted|edited|discarded"}` —
  allowed for the job's creator or an admin; 404 otherwise.
- Both confirm views (report + case study) set the outcome automatically by
  comparing confirmed text to `job.output_text` (whitespace-normalized): equal →
  `accepted`, different → `edited`.
- `GET /api/ai/metrics/` (admin only) — per `job_type`, for last-30-days and
  all-time: runs, ok/error counts, average `latency_ms`, outcome breakdown.

**Frontend**

- Brief modal (chart + schedule): footer "Was this useful?" 👍/👎 → feedback endpoint
  (`accepted` / `discarded`), buttons disappear after voting.
- Remark polish: keep the polish job id + draft text in state; when the remark is
  **saved**, send `accepted` if the saved text equals the draft, else `edited`.
- Census narrative on `AgencySummary.jsx`: same thumbs pattern.
- `Settings.jsx` (admin, AI section): a usage panel — one row per feature: runs,
  success %, avg latency, accepted/edited/discarded counts (30-day window with
  all-time in a muted second line, or a simple toggle).

---

## Error handling

All new AI endpoints reuse `_gate()` 503 degradation. `latest` and `metrics` work with
AI switched off (they only read history). Prefetch failures are silent by design.

## Testing

Extend `ai/tests/test_ai.py` using the existing mocked-client pattern:
latest-brief (permission matrix, today-only scoping), prefetch (dedup, role scoping,
thread patched to run synchronously), case-study summarize/confirm (permission matrix,
missing-text 400, confirmed-flag reset), feedback endpoint (creator-only, invalid
outcome 400), metrics (admin-only, aggregate correctness), outcome-on-confirm
(accepted vs edited), F1 prompt contents, `_normalize_output`.

## Non-goals

No Celery/queues, no model upgrade, no scoring or classification of children, no
auto-applying drafts anywhere, no cloud AI.
