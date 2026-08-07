# Questionnaire Builder + Paper Digitization — Design

- **Date:** 2026-06-27
- **Status:** Approved (design)
- **Phase:** Phase 2, sub-feature **#1 of 3** (the others: Assessment-Taking Flow, Child Respondent Interface — separate specs).
- **Related:** [System Design](2026-06-22-nacc-system-design.md), [Activity Log](2026-06-26-activity-log-notifications-design.md)

---

## 1. Problem & Goal

Psychologists at NACC-RACCO I run behavioral assessments using **paper instruments** they already trust. Today the app's questionnaire is 4 hard-coded items in `seedData` and nothing persists. 

**Goal:** let a psychologist (or admin) turn a **paper instrument into a usable digital questionnaire** — upload a PDF/photo, have it auto-digitized into an editable draft, review/fix it, and publish it — plus manage questionnaires by hand. This is the foundation the other two Phase-2 sub-features consume.

## 2. Scope

**In scope:**
- Manage questionnaires + their questions (create / edit / reorder / archive) via a real API and an Admin/Psychologist UI.
- **Digitize from paper:** upload PDF/PNG/JPG → local OCR → heuristic parse → editable **draft** → review → save/publish.
- Activity logging for questionnaire create/edit/archive (reusing the existing `activity` app).

**Out of scope (deferred):**
- Assessment-taking flow and Child Respondent interface (sub-features #2/#3).
- **All scoring / AI analysis / recommendations** (Phase 3). Extraction uses **local OCR + heuristics only — no paid API**.
- Cloud/LLM extraction — designed-for via a swappable interface, but not implemented now.

## 3. Access control & the revert toggle (IMPORTANT)

**Decision:** questionnaire management (CRUD **and** the upload/extract endpoint) is available to **Administrator + Psychologist**. Staff are excluded.

**Divergence from the capstone:** the capstone RBAC matrix lists "Manage questionnaire templates" as **Admin-only** (rationale: standardization). Granting Psychologists access is a deliberate product decision (2026-06-27) because digitizing their own instrument is core to their assessment work.

**Revert must be a one-line change in one place on each side.** Both sides define a single named role list; reverting to Admin-only = delete the Psychologist entry.

- **Backend** — in `accounts/permissions.py`:
  ```python
  # Roles allowed to manage assessment instruments (questionnaires).
  # Capstone RBAC matrix = Admin-only; Psychologist added per product decision 2026-06-27.
  # TO REVERT to the capstone rule: remove Role.PSYCHOLOGIST from this tuple.
  INSTRUMENT_MANAGER_ROLES = (Role.ADMINISTRATOR, Role.PSYCHOLOGIST)

  class CanManageInstruments(BasePermission):
      def has_permission(self, request, view):
          return bool(request.user and request.user.is_authenticated
                      and _role_name(request) in INSTRUMENT_MANAGER_ROLES)
  ```
  All questionnaire endpoints use `CanManageInstruments`.

- **Frontend** — a single shared constant in `frontend/src/config/roles.js`:
  ```js
  // TO REVERT instrument management to admin-only: remove 'Psychologist'.
  export const INSTRUMENT_MANAGER_ROLES = ['Administrator', 'Psychologist'];
  ```
  Imported by the route guard (`App.jsx`) and the sidebar item (`Sidebar.jsx`). No inline role lists for this feature.

## 4. Data model (additive — one migration, no breaking changes)

Existing `Questionnaire` and `Question` need a few fields to represent real instruments:

| Model | New field | Type / purpose |
|---|---|---|
| `Questionnaire` | `status` | CharField choices `draft` / `active` / `archived`; default `draft`. Digitized uploads land as `draft`; "Publish" → `active`; the assessment flow (later) shows only `active`. Archive = soft-delete, matching children/users. |
| `Question` | `options` | JSONField (list of strings), default `list`. Holds answer choices for `multiple_choice` / `emotion`; empty for `rating_scale` / `yes_no`. |
| `Question` | `order` | PositiveIntegerField, default 0. Question sequence within a questionnaire. |

**Canonical `question_type` values:** `multiple_choice`, `rating_scale`, `yes_no`, `emotion` (the four the capstone names). Stored in the existing `Question.question_type` CharField.

## 5. Backend API (`assessments` app — currently has no endpoints)

New `assessments/serializers.py`, `assessments/views.py`, `assessments/urls.py`; include `assessments.urls` in `config/urls.py`.

- **`QuestionSerializer`** — `id, question_text, question_type, options, order`.
- **`QuestionnaireSerializer`** — `id, title, age_group, description, status, questions[]` (nested, writable). On create/update it replaces the question set from the payload (simple, predictable for a builder).
- **`QuestionnaireViewSet`** (`/api/questionnaires/`) — full CRUD, `permission_classes = [CanManageInstruments]`, no pagination. `get_queryset` excludes `archived` unless `?include_archived=true` (matches `_ArchivableViewSet`). `archive` action (soft-delete) + optional `publish` action (`status='active'`). Logs create/update/archive via `log_activity(..., category=ActivityLog.RECORD, entity_type="Questionnaire", entity_label=title)`.
- **`POST /api/questionnaires/extract/`** — `permission_classes = [CanManageInstruments]`, accepts `multipart/form-data` with a `file`. Validates type (PDF/PNG/JPG) and size (≤ 10 MB), runs the extractor, returns a **draft** JSON (below). **Does not persist.** Errors return a clear 400 with a message (e.g., unreadable file, OCR unavailable).

**Draft shape returned by `/extract/`:**
```json
{
  "title": "Strengths and Difficulties Questionnaire",
  "age_group": "",
  "questions": [
    { "question_text": "I try to be nice to other people.", "question_type": "rating_scale", "options": [], "order": 1 },
    { "question_text": "Do you have trouble sleeping?", "question_type": "yes_no", "options": [], "order": 2 }
  ]
}
```

## 6. The extractor (free, swappable)

`assessments/extraction/` package:
- **`base.py`** — `InstrumentExtractor` interface: `extract(file_bytes, content_type) -> dict` (the draft shape above). One method, well-defined contract.
- **`ocr_heuristic.py`** — `OcrHeuristicExtractor` (the Phase-2 implementation):
  - **Text extraction:** PyMuPDF (`fitz`) reads text directly from text-based PDFs. For pages with little/no text (scanned), render the page to an image and OCR with **Tesseract** (`pytesseract` + Pillow). Uploaded images go straight to Tesseract.
  - **Heuristic parser:** split text into candidate questions (numbered lines `1.` / `1)`, bullets, or lines ending in `?`); strip numbering; guess `question_type` — a `1 2 3 4 5` run or "Never…Always" / "Strongly disagree…agree" → `rating_scale`; "Yes / No" → `yes_no`; lettered/bulleted choices captured as `options` → `multiple_choice`; otherwise default `rating_scale`. Title guessed from the first heading line or the filename.
  - **Graceful degradation:** text-based PDFs work with **no Tesseract installed**. If a scanned/image input needs OCR and Tesseract is missing, return a clear 400 ("OCR engine not available — install Tesseract, or type the questions manually"), so the manual builder is always a fallback.
- **Swap path:** a future `LlmExtractor` (Claude/Gemini/Ollama) implements the same interface; the viewset picks the implementation from one factory/setting. No other code changes.

**Dependencies (add to `backend/requirements.txt`):** `pymupdf`, `pytesseract`, `Pillow`. Plus the free **Tesseract** binary on the OS (documented in README as optional, only needed for scanned/photo input).

## 7. Frontend (Admin + Psychologist)

- **Route:** new `/questionnaires`, guarded by `INSTRUMENT_MANAGER_ROLES` (§3).
- **Sidebar:** new item **"Assessment Instruments"** under the **Clinical** section (next to "Assessment Tools"), `roles: INSTRUMENT_MANAGER_ROLES`.
- **`pages/Questionnaires.jsx`** — list view (title, age group, status badge, # questions) using the existing Card/table/drawer + `ui` primitives, matching Children/Users.
- **Builder drawer (`QuestionnaireForm`)** — create/edit a questionnaire: title, age group, description, status; an editable question list (text, type `<Select>`, options editor shown only for `multiple_choice`/`emotion`, drag-or-arrow reorder, add/remove). Actions: **Save draft** / **Publish**.
- **"Digitize from paper"** — a button opens a file picker; on select, `POST /questionnaires/extract/` (multipart) with a loading state; on success it opens the **same builder drawer pre-filled** with the draft and a banner "Review auto-extracted draft — check each question before publishing." So extraction and manual editing share one screen; nothing is saved until the user clicks Save/Publish.
- API calls go through the existing `api` client (JWT attached automatically).

## 8. Testing

Backend (existing `APITestCase` style, new `assessments/tests/test_api.py`):
- Questionnaire CRUD round-trip with nested questions (create → list → update → archive).
- **Permissions:** Admin ✅, Psychologist ✅, Staff ❌ (403) for both CRUD and `/extract/`.
- **Extractor unit test:** `OcrHeuristicExtractor` parses a small bundled **text-based PDF fixture** into the expected questions + types (no Tesseract needed for this fixture).
- **`/extract/` endpoint:** returns a draft and **persists nothing** (questionnaire count unchanged).

Frontend: verified via `npm run build` + browser smoke test (upload a sample → review draft → publish → appears in list).

## 9. File change summary

**New (backend):** `assessments/serializers.py`, `assessments/views.py`, `assessments/urls.py`, `assessments/extraction/{__init__,base,ocr_heuristic}.py`, a migration, `assessments/tests/test_api.py`, a tiny PDF test fixture. **Modify:** `assessments/models.py` (3 fields), `accounts/permissions.py` (`CanManageInstruments` + `INSTRUMENT_MANAGER_ROLES`), `config/urls.py`, `backend/requirements.txt`, `README.md` (Tesseract note).

**New (frontend):** `src/config/roles.js`, `src/pages/Questionnaires.jsx`. **Modify:** `src/App.jsx` (route), `src/components/Sidebar.jsx` (nav item).

## 10. Future revert (recorded for clarity)

To restore the capstone's **Admin-only** rule for instrument management: (1) backend — remove `Role.PSYCHOLOGIST` from `INSTRUMENT_MANAGER_ROLES` in `accounts/permissions.py`; (2) frontend — remove `'Psychologist'` from `INSTRUMENT_MANAGER_ROLES` in `src/config/roles.js`. No other changes required.
