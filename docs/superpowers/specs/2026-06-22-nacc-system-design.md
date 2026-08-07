# AI-Integrated Child Behavioral Assessment and Counseling Support System (NACC-RACCO I) — System Design

- **Date:** 2026-06-22
- **Status:** Approved (design); Phase 1 pending implementation plan
- **Source of truth:** Capstone document — *AI-Integrated Child Behavioral Assessment and Counseling Support System for the National Authority for Child Care – Regional Alternative Child Care Office I (RACCO I)*, Chapters 1–3.

---

## 1. Background & Problem

NACC-RACCO I (Bauang, La Union) serves alternative child care (adoption, foster care, kinship/residential care) across Region I. Counselors and child welfare workers currently rely on **manual, paper-based, non-uniform** behavioral assessment and record-keeping. The capstone identifies three core problems:

1. **No centralized, standardized assessment platform** — inconsistent, hard to retrieve, hard to compare across counselors.
2. **Inconsistent monitoring of child progress** — depends on individual notes; risks missed follow-ups and undetected behavioral decline.
3. **Limited, inefficient report generation** — manual compilation threatens accuracy, timeliness, and legal compliance (RA 12199).

The existing software is a **frontend-only React prototype** with hardcoded mock data, a fake 4-step assessment wizard (3 hardcoded Likert questions), and a "fake AI" that sums answers. No database, authentication, roles, or persistence. This project turns that prototype into a real, working system that matches the capstone.

### Legal / compliance drivers
- **RA 11642** (Domestic Administrative Adoption & Alternative Child Care Act) — mandates continuous counseling/psychosocial support.
- **RA 11036** (Mental Health Act) — timely support + strict privacy of personal health data.
- **RA 12199** (ECCD System Act) — clear, organized data + regular accountability reports.
- **RA 10173** (Data Privacy Act of 2012) — secure, role-restricted handling of sensitive minors' data.

---

## 2. Goals & Non-Goals

### Goals
- Secure child profile management (register/update/archive children + case history + guardians + assessment records).
- Age-appropriate digital behavioral assessment surveys (multiple choice, rating scale, yes/no, emotion-based).
- Automated analysis that classifies results as **Normal / Needs Monitoring / Needs Counseling Attention**.
- Counseling recommendation output (behavioral observations, emotional summary, suggested actions, priority level).
- Progress monitoring over time + date-range report generation/export.
- Role-based access control with full Data Privacy Act alignment.

### Non-Goals (from the capstone's Scope & Limitation)
- **Not** a financial-subsidy, legal-custody, or full welfare-case database.
- **Not** a replacement for NACC national databases; **no** live integration with external government networks.
- Automated output is **decision support, not a psychiatric diagnosis** — all final clinical determinations remain with licensed professionals.
- Built specifically for NACC-RACCO I (not general deployment without customization).

---

## 3. Key Decisions

| Decision | Choice | Rationale |
|---|---|---|
| **Architecture** | React frontend + Django REST API backend | Honors the PDF's "Django (Python)" server; reuses the existing React UI; clean, defensible separation of concerns. |
| **Database** | SQLite for development; structured to migrate to PostgreSQL for production | Zero-config for a capstone demo and submission; Django ORM makes the later swap straightforward. |
| **Auth** | JWT (`djangorestframework-simplejwt`) | Standard, stateless auth for a React SPA + DRF. Passwords hashed by Django. |
| **Analysis engine** | **Hybrid** — rule-based scoring for classification + LLM (Claude API) for narrative summary/recommendations | Rule-based scoring is transparent, reproducible, needs no training data, and is ethically/legally defensible for vulnerable minors. The LLM adds genuine value for the natural-language emotional summary and recommendation text. Data is anonymized before leaving the system. |
| **Build approach** | Phased (foundation first) | Always have a working, demoable system; spec and review each phase; lower risk for a capstone. |

---

## 4. Architecture

```
NACC SYS/
├── frontend/   → React + Vite + Tailwind SPA (existing UI, reorganized; real API calls; login + role-based routing)
└── backend/    → Django + Django REST Framework; SQLite; JWT auth; business logic; scoring engine; LLM service; reports
```

- **Frontend** keeps the current visual design, replaces mock data with API calls, and adds authentication + role-based menus/routes.
- **Backend** owns authentication, role-based permissions, all business logic, the rule-based scoring engine, the LLM recommendation service, and report generation.

---

## 5. Data Model

Faithful to the capstone ERD / Relational Database Schema (10 tables), with explicitly-noted necessary additions for a real system.

| Table | Fields (per capstone + additions) | Notes |
|---|---|---|
| `tbl_role` | role_id (PK), role_name | As specified. |
| `tbl_user` | user_id (PK), role_id (FK), fullname, username, **password (hashed)**, email, role, status | Implemented as a Django **custom user model** linked to role. Passwords hashed (the PDF's plain field is not safe for real data). |
| `tbl_child` | child_id (PK), **guardian_id (FK)**, fullname, birth_date, gender, status, address, case_type | `guardian_id` FK added (present in the Logical Data Structure). |
| `tbl_guardian` | guardian_id (PK), fullname, birth_date, gender, address, status, case_type | As specified. |
| `tbl_questionnaire` | questionnaire_id (PK), title, age_group, description | As specified. |
| `tbl_question` | question_id (PK), questionnaire_id (FK), question_text, question_type | `question_type` supports multiple choice / rating scale / yes-no / emotion-based. |
| `tbl_assessment` | assessment_id (PK), child_id (FK), counselor_id (FK), assessment_date, assessment_type, status | As specified. |
| `tbl_response` | response_id (PK), assessment_id (FK), question_id (FK), answer | As specified. |
| `tbl_assessment_result` | result_id (PK), assessment_id (FK), behavioral_score, **classification**, assessment_date, assessment_type, generated_date | `classification` field added (Normal / Needs Monitoring / Needs Counseling Attention) — produced by the engine but missing from the original schema. |
| `tbl_recommendation` | recommendation_id (PK), result_id (FK), recommendation_text, priority_level | `recommendation_text` holds the LLM narrative; `priority_level` holds urgency. |

**Cross-cutting additions:** `created_at` / `updated_at` timestamps on all tables; "Archive" operations (from the IPO diagrams) implemented as a `status` **soft-delete** so records are never physically destroyed.

---

## 6. Roles & Access Control

| Capability | Admin | Counselor | Staff | Child Respondent |
|---|:---:|:---:|:---:|:---:|
| User management (add/edit/view/archive) | ✅ | ❌ | ❌ | ❌ |
| Child & guardian profiles | ✅ | view assigned | ✅ manage | ❌ |
| Manage questionnaire templates | ✅ | ❌ | ❌ | ❌ |
| Administer assessment / view AI results | ✅ | ✅ | view trends | ❌ |
| Take the survey (guided UI only) | ❌ | ❌ | ❌ | ✅ |
| Counseling recommendations | ✅ | ✅ | ❌ | ❌ |
| Facility-wide reports & analytics | ✅ | own cases | ✅ | ❌ |

The **Child Respondent** interacts **only** with the simplified, guided, non-intimidating survey interface (emotion-based selections, interactive scales). They have no administrative privileges and cannot view records, AI insights, or recommendations.

---

## 7. Phase 1 Scope (Foundation — build first)

1. Django backend scaffolding + SQLite + JWT auth + the **full data model** (all 10 models migrated now, so later phases only add logic).
2. **Login** screen (per IPO "Log In": email/password → verify → access account).
3. **User Management** (Admin) — add / edit / view / archive users with roles (per IPO User Management).
4. **Child Profile + Guardian Management** — add / edit / view / archive (Staff & Admin) (per IPO Children Record Management).
5. Frontend wired to the API; login + role-based menus/routes; mock data removed.

**Phase 1 done = ** you can log in as each role, an Admin can manage users, and Staff/Admin can manage real child + guardian records stored in the database.

---

## 8. Roadmap (later phases)

- **Phase 2 — Assessments:** questionnaire builder (Admin), assessment-taking flow, and the **Child Respondent** guided survey interface.
- **Phase 3 — Analysis & Recommendations:** rule-based scoring engine → `classification` + `behavioral_score`; LLM recommendation service (anonymized) → `recommendation_text` + `priority_level`.
- **Phase 4 — Monitoring & Reporting:** progress monitoring over time, dashboard wired to real data, and date-range report generation/export (per IPO Report Management).

---

## 9. Compliance & Ethics Notes
- Sensitive minors' data is access-restricted by role and never exposed to Child Respondents.
- Data sent to the LLM is **anonymized** (no names/identifiers) to respect the Data Privacy Act.
- System output is clearly labeled **decision support, not a diagnosis**; licensed professionals make all clinical determinations.
- Soft-delete (archive) preserves records for accountability/audit.
```
