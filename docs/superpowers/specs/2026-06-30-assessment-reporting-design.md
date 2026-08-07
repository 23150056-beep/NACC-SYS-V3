# Assessment Reporting — Design Spec

**Date:** 2026-06-30
**Status:** Draft for review
**Phase:** 4 (Monitoring & Reporting)
**Supersedes:** the placeholder **Compliance & Audit** module, which is removed as part of this work (per research adviser's decision).

---

## 1. Goal & Motivation

The system stores rich per-assessment data (date, behavioral score 0–100, engine classification, confidence, AI recommendation, priority level, and the psychologist's notes), and a child can have many assessments over time. Today that history is invisible — the Assessment Results page only lists assessments flatly, so you cannot see whether a child is **improving or worsening**, and the Dashboard shows **hardcoded placeholder numbers**.

This feature adds **relevant, role-appropriate report generation** built on the real assessment data, and in doing so replaces the placeholder dashboard data and removes the non-functional Compliance & Audit page.

### Adviser direction captured
- Remove the Compliance & Audit module entirely.
- Focus on relevant report generation for **assessment results**.
- Psychologists: per-child progress over time.
- Admin **and Staff**: weekly / monthly / yearly agency-wide assessment summary (staff explicitly requested to have the same logic as admin for the summary).

---

## 2. Scope

### In scope
1. **Child Progress Report** (per child, over time) — psychologist (full + edit) and staff (read-only).
2. **Agency Assessment Summary** (weekly / monthly / yearly + custom range) — admin and staff.
3. **Editable-with-audit** policy for assessments (notes + classification), with a lock on finalize/export.
4. **Export:** browser print-to-PDF for both reports; **CSV** export for the Agency Summary's numbers.
5. **Wire the Dashboard to real data** using the new summary aggregates (delete the `seedData` dashboard placeholders).
6. **Remove the Compliance & Audit page** and its sidebar entry.

### Out of scope (YAGNI / future)
- Session scheduling backend — the "Next Session" value stays as it is today (a derived placeholder) or is omitted from the report; no real scheduling is built here.
- Real NACC integration / network submission — "Finalize & Submit to NACC" is an in-system status that **locks** the record; it does not transmit anywhere.
- Server-generated PDF (WeasyPrint/ReportLab) — explicitly rejected (Windows native-dependency risk); we use browser print.
- Child Respondent–facing reports.

---

## 3. Role / Report Access Matrix

| Role | Child Progress Report | Agency Summary (W/M/Y) |
|---|---|---|
| **Psychologist** | View **all assigned/own** + edit own assessment notes/classification (until locked) | — |
| **Staff** | View **read-only** | View + Print + CSV (**same as admin**) |
| **Administrator** | View (all children) | View + Print + CSV (full) |

> Note: "same as admin" for staff **includes** the per-psychologist activity table. This is a deliberate, agency-approved choice for operational transparency.

---

## 4. Report 1 — Child Progress Report

**Purpose:** make a single child's behavioral trajectory over time visible and printable.

**Sections:**
1. **Child header** — name, case ref (`C-00XX`), age + age group, gender, case type, assigned psychologist, location (barangay/municipality/province), who surrendered, status. Plus "Report generated [date] by [name]" for the printout.
2. **Progress snapshot (headline)** —
   - count of assessments to date · date range covered
   - latest classification + priority + score
   - **Trajectory badge: Improving ↑ / Stable → / Worsening ↓** (see computation below)
3. **Trend chart** — line of behavioral score (0–100) over assessment dates, with classification bands shaded (Normal `<34` / Needs Monitoring `34–66` / Needs Counseling Attention `≥67`). Built with `recharts`.
4. **Assessment history table** — one row per assessment: date · instrument · session type · engine classification · score · confidence · priority · psychologist's classification.
5. **Latest assessment detail** — most recent AI `recommendation_text` + the psychologist's full clinical `notes`.
6. **Footer** — RA 10173 confidentiality + "decision support, not a diagnosis" + signature line (psychologist + date) for print.

**Trajectory computation (explicit, to avoid ambiguity):**
- Requires ≥2 completed assessments with a `behavioral_score`. With 0–1, show **"Baseline — insufficient history."**
- Compare the latest assessment's `behavioral_score` to the immediately previous one. Because a **higher** score means **more** behavioral concern:
  - latest score **lower** than previous by **> 5** → **Improving ↑**
  - latest score **higher** than previous by **> 5** → **Worsening ↓**
  - within **±5** → **Stable →**

---

## 5. Report 2 — Agency Assessment Summary

**Purpose:** agency-wide oversight + accountability reporting over a chosen period; also the real data source for the Dashboard.

**Period:** Weekly / Monthly / Yearly toggle, plus a custom `from`–`to` date range. Filtered on `Assessment.assessment_date`.

**Sections:**
1. **Header** — selected period + "Generated [date] by [user]".
2. **Key metrics** —
   - total assessments completed · distinct children assessed
   - **outcome breakdown** by engine classification (Normal / Needs Monitoring / Needs Counseling Attention): count + %
   - **priority breakdown** (Low / Medium / High)
   - **case-type breakdown** (e.g. how many of each `case_type` this period)
   - average behavioral score · average confidence · # low-confidence (overridden) results
3. **Trend over the period** — assessments per week/month chart (real version of the current Dashboard placeholder).
4. **Per-psychologist activity table** — each psychologist → # assessments, case-mix (classification breakdown), average score.
5. **Children needing attention** — children whose **latest** assessment is Needs Counseling Attention / High priority.
6. **Export** — Print/Save-as-PDF (formatted) + **CSV** of the underlying numbers.
7. **Footer** — confidentiality + "generated for NACC reporting".

---

## 6. Edit-with-Audit Policy

- A psychologist may edit **only their own** assessment's `notes` and `classification` (their authored clinical fields).
- The AI-computed result (`behavioral_score`, engine `classification`, `confidence`, `recommendation_text`, `priority_level`) is **never editable**.
- Editing is **blocked once the assessment is locked**.
- **Every edit writes an `ActivityLog` row** (`action="updated"`, category record, entity Assessment) for the audit trail.
- **Lock triggers:** an explicit **"Finalize & Submit to NACC"** action sets `is_locked = true` (`locked_at` timestamp); exporting/printing a finalized report keeps it locked. After locking, a change requires a **new** assessment (append-only correction).

---

## 7. Architecture

### 7.1 Backend (Django)

**Data model — `assessments.Assessment` gains:**
- `is_locked` (BooleanField, default `False`)
- `locked_at` (DateTimeField, null=True, blank=True)
- migration `assessments/000X_assessment_lock.py`

**Endpoints:**
- `PATCH /api/assessments/<id>/` — edit `notes` + `classification` only; permission: the **owning psychologist**; rejects if `is_locked`; ignores any attempt to set result fields; logs to ActivityLog.
- `POST /api/assessments/<id>/finalize/` — owning psychologist; sets `is_locked=true`, `locked_at=now`; logs.
- `GET /api/reports/child/<child_id>/` — returns the child profile + assessment history (oldest→newest) + computed trajectory. Permission: psychologist (assigned/own), staff (read), admin (all).
- `GET /api/reports/summary/?range=weekly|monthly|yearly&from=&to=` — returns the aggregates described in §5 (key metrics, trend, per-psychologist, attention list). Permission: **admin + staff**.
- `GET /api/reports/summary/?...&format=csv` — same data as CSV (`Content-Type: text/csv`), built with Python's `csv` module.

**Aggregation:** Django ORM `annotate`/`aggregate`/`values` over `Assessment` joined to `AssessmentResult`. New `assessments/reports.py` (or a `ReportViewSet`) holds the query logic, kept separate from the existing assessment CRUD views.

### 7.2 Frontend (React)

- **`ChildProgressReport`** view — reached from the Assessment Results list (click a child). Renders the §4 sections; psychologist gets inline edit on unlocked assessments + "Finalize" + "Print / Save PDF".
- **`AgencySummary`** view — new report screen (admin + staff) with the period toggle, KPI cards, `recharts` trend, per-psychologist table, attention list, Print + CSV buttons.
- **Print CSS** (`@media print`) for both — hide app chrome (sidebar/topbar), expand the report to full width, page-break-friendly.
- **Dashboard rewire** — point the stat cards / trend / case-types panels at `GET /api/reports/summary/` (default monthly), deleting the corresponding `seedData` exports.
- **Remove** `Compliance.jsx`, its route in `App.jsx`, and its `Sidebar` nav item; drop the `compliance` export from `seedData.js`.
- Charts use `recharts` (already a dependency). No new packages.

### 7.3 Navigation / placement
- Child Progress Report: a sub-view of **Assessment Results** (drill-in), not a new top-level nav item.
- Agency Summary: a new sidebar item under **Governance** (replacing the removed Compliance & Audit slot), visible to Admin + Staff.

---

## 8. Testing

- **Backend unit tests:**
  - trajectory calc (improving/stable/worsening/baseline edge cases)
  - summary aggregation correctness for a known fixture (counts, breakdowns, per-psychologist, date-range filtering, weekly/monthly/yearly bucketing)
  - edit permission: owning psychologist can edit unlocked; non-owner rejected; locked rejected; result fields ignored; ActivityLog written
  - finalize locks; CSV format
  - role access: staff/admin can read summary; psychologist cannot
- **Frontend:** manual verification via the run/preview workflow against the live API (login per role → generate each report → print preview → CSV download), plus build/lint.

---

## 9. Success Criteria

1. A psychologist opens a child and sees the child's score trend over time with a correct **Improving/Stable/Worsening** badge, and can print it to PDF.
2. A psychologist can correct their own (unlocked) assessment notes/classification; the change is logged; a finalized assessment can no longer be edited.
3. Admin **and staff** can generate a weekly/monthly/yearly Agency Summary with real numbers, including per-psychologist activity, and export it to PDF + CSV.
4. The Dashboard shows **real** counts/trends (no `seedData` placeholders).
5. The Compliance & Audit page is gone (page, route, nav, seed data).
6. All new backend logic is covered by passing tests.

---

## 10. Open Questions (for review)
- "Next Session" in the Child Progress Report: keep the current derived placeholder, or omit it from the report until real scheduling exists? (Currently leaning: **omit** from the printed report to avoid showing a fabricated date.)
- Should the **psychologist** also get a scoped "my activity" version of the Agency Summary (their own numbers only)? Currently out of scope.
