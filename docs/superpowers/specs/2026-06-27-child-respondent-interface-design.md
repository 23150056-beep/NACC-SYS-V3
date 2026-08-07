# Child Respondent Interface — Design

- **Date:** 2026-06-27
- **Status:** Approved (design)
- **Phase:** Phase 2, sub-feature **#3 of 3** (completes Phase 2).
- **Related:** [System Design](2026-06-22-nacc-system-design.md), [Assessment-Taking Flow](2026-06-27-assessment-taking-flow-design.md)

---

## 1. Problem & Goal

The capstone's 4th role, **Child Respondent**, is *not* a login account — it is a simplified, guided, non-intimidating survey interface the child uses directly (emotion-based selections, interactive scales). It must never expose records, AI, or recommendations.

**Goal:** let a psychologist launch an in-app, full-screen **kiosk survey** for a child + published questionnaire, hand the device to the child, and have the child answer with large child-friendly controls. On finish, control returns to the psychologist, who adds clinical notes + a classification and signs — producing one completed `Assessment` (reusing Phase-2 #2). Shareable-link access is designed-for but built later.

## 2. Scope

**In:** a reusable child-friendly survey component; a "Hand to child" kiosk handoff inside the existing assessment wizard; a `respondent_mode` flag recording child-self-reported assessments.

**Out (deferred):** the public shareable-link/token path (a later phase — see §6); AI scoring/analysis (Phase 3); OS-level kiosk lockdown (the survey hides app chrome, but true device lockdown is outside the web app).

## 3. The survey component (`RespondentSurvey`) — standalone & reusable

A new presentational component, **`frontend/src/components/RespondentSurvey.jsx`**. Contract:
- **Props:** `questions` (array, from a questionnaire), `childName` (string, for a friendly greeting), `initial` (optional prior answers), `onComplete(answers)`, `onExit()`.
- **No API calls** — questions in, answers out. This decoupling is what lets a future public `/survey/:token` route mount the exact same component with zero rework.

Child-friendly rendering, **one question per screen**:
| `question_type` | Control |
|---|---|
| `rating_scale` | A row of 5 large faces 😞 😕 😐 🙂 😄 (each with its number 1–5). |
| `yes_no` | Two large buttons — 👍 **Yes** / 👎 **No**. |
| `multiple_choice` / `emotion` | Large stacked option buttons from the question's `options`. |
| (no options, fallback) | A single large text input. |

UX: a warm greeting using the child's first name ("Hi Andres! 👋 Let's answer some questions together."), big touch targets, **auto-advance** on tap, simple **progress dots**, a gentle **Back**, and a final "All done! 🎉" screen with a **Finish** button that calls `onComplete(answers)`. App chrome (sidebar/topbar) is not rendered — the component is shown as a **full-screen overlay** so nothing clinical is visible to the child. A small, low-prominence **Exit** (top corner) calls `onExit()` for the psychologist to abort.

Answers are stored exactly like the psychologist flow: `{ [questionId]: answerText }` (e.g., rating → `"4"`, yes/no → `"Yes"`, option → the option text).

## 4. Integration into the wizard (`Assessment.jsx`)

Reuse the existing 4-step wizard from #2 — add the kiosk handoff at the answer step:
- On **step 3 (Responses)**, add a prominent **"Hand to child 🧒"** button alongside the normal inputs.
- Tapping it sets `kiosk = true` and renders `RespondentSurvey` as a **fixed full-screen overlay** (`questions`, `childName = childObj.fullname`, `initial = answers`).
- `onComplete(a)` → `setAnswers(a)`, set `respondentMode = "child"`, `setKiosk(false)`, advance to **step 4 (Review & Sign)**.
- `onExit()` → `setKiosk(false)` (returns to step 3, answers preserved).
- **Step 4** is unchanged from #2: the psychologist adds notes + classification and signs. The submit payload simply includes `respondent_mode` (default `"staff"`; `"child"` if the kiosk was used).

So the Child Respondent interface is a child-friendly skin over the existing answer collection — no new wizard, no new persistence path.

## 5. Backend (minimal — one field)

Add `Assessment.respondent_mode` — `CharField`, choices `"staff"` (default) / `"child"` — recording whether the child self-reported. The wizard sends it; `AssessmentWriteSerializer` accepts it; everything else **reuses the #2 `POST /api/assessments/` endpoint** (the psychologist is authenticated — no public surface added now). One small migration.

## 6. Future-proofing for shareable links (not built now)

Because `RespondentSurvey` is standalone and `respondent_mode` already exists, a later phase adds, with no change to the survey UI or the `Assessment` model:
- a `RespondentInvite` model (token, child, questionnaire, expiry, used_at),
- a public `GET /survey/<token>/` (returns the questionnaire) + `POST /survey/<token>/` (creates an `Assessment` with `respondent_mode="child"`, status `ongoing`/pending),
- a public React route that mounts `RespondentSurvey`.

## 7. Testing

Backend (`assessments/tests/test_api.py`): an assessment created with `respondent_mode="child"` persists that value; omitting it defaults to `"staff"`; existing assessment tests still pass.

Frontend: `npm run build` + browser smoke — in the wizard, select child + questionnaire, click **Hand to child**, answer each question through the child UI, finish, confirm it returns to step 4, sign, and verify the saved assessment has `respondent_mode="child"`.

## 8. File change summary

**Backend — modify:** `assessments/models.py` (one field), `assessments/serializers.py` (`AssessmentWriteSerializer` adds `respondent_mode`); new migration; `assessments/tests/test_api.py`.

**Frontend — new:** `src/components/RespondentSurvey.jsx`. **Modify:** `src/pages/Assessment.jsx` (kiosk handoff on step 3 + send `respondent_mode`).
