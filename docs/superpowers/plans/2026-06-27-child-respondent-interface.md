# Child Respondent Interface Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a psychologist hand the device to a child for a full-screen, child-friendly survey, then take it back to sign — saving one assessment flagged as child-self-reported.

**Architecture:** A standalone `RespondentSurvey` React component (questions in → answers out, no API) shown as a kiosk overlay from the existing assessment wizard's answer step. One additive `Assessment.respondent_mode` field; persistence reuses the Phase-2 #2 `POST /api/assessments/`.

**Tech Stack:** Django + DRF (SQLite); React + Vite.

**Spec:** [2026-06-27-child-respondent-interface-design.md](../specs/2026-06-27-child-respondent-interface-design.md)

**Conventions:** Backend from `backend/` as `./venv/Scripts/python.exe manage.py <cmd>`. Commits omit any Claude co-author trailer. **Commits are deferred** — held until the user asks; commit steps below are checkpoints.

---

## File Structure

**Backend — modify:** `assessments/models.py` (one field), `assessments/serializers.py` (`AssessmentWriteSerializer` + field); new migration `0005_*`; `assessments/tests/test_api.py`.
**Frontend — new:** `src/components/RespondentSurvey.jsx`. **Modify:** `src/pages/Assessment.jsx`.

---

## Task 1: `Assessment.respondent_mode` field + serializer

**Files:** Modify `backend/assessments/models.py`, `backend/assessments/serializers.py`; Test append `backend/assessments/tests/test_api.py`.

- [ ] **Step 1: Write the failing test**

Append to `backend/assessments/tests/test_api.py` (inside `class AssessmentTakingTest`, add two methods):
```python
    def test_respondent_mode_defaults_to_staff(self):
        self._auth("p@racco1.gov.ph")
        self.client.post("/api/assessments/", self._assessment_payload(), format="json")
        self.assertEqual(Assessment.objects.get().respondent_mode, "staff")

    def test_respondent_mode_child_is_saved(self):
        self._auth("p@racco1.gov.ph")
        payload = self._assessment_payload()
        payload["respondent_mode"] = "child"
        self.client.post("/api/assessments/", payload, format="json")
        self.assertEqual(Assessment.objects.get().respondent_mode, "child")
```

- [ ] **Step 2: Run it to verify failure**

Run: `./venv/Scripts/python.exe manage.py test assessments.tests.test_api.AssessmentTakingTest.test_respondent_mode_child_is_saved -v 2`
Expected: FAIL (`respondent_mode` not a field / not saved).

- [ ] **Step 3: Add the model field**

In `backend/assessments/models.py`, add to the `Assessment` class (after `classification`):
```python
    STAFF, CHILD = "staff", "child"
    RESPONDENT_CHOICES = [(STAFF, "Staff"), (CHILD, "Child")]
```
and the field (place it right after the `classification` field line):
```python
    respondent_mode = models.CharField(max_length=10, choices=RESPONDENT_CHOICES, default=STAFF)
```

- [ ] **Step 4: Add the serializer field**

In `backend/assessments/serializers.py`, add `"respondent_mode"` to `AssessmentWriteSerializer.Meta.fields`:
```python
        fields = ["id", "child", "questionnaire", "assessment_type", "notes",
                  "classification", "respondent_mode", "responses"]
```

- [ ] **Step 5: Make migration and run the tests**

Run: `./venv/Scripts/python.exe manage.py makemigrations assessments`
Expected: `0005_…` adding `respondent_mode`.
Run: `./venv/Scripts/python.exe manage.py test assessments.tests.test_api.AssessmentTakingTest -v 1`
Expected: all OK (8 tests).

- [ ] **Step 6: Commit (deferred — checkpoint only)**

```bash
git add backend/assessments/models.py backend/assessments/serializers.py backend/assessments/migrations/0005_*.py backend/assessments/tests/test_api.py
git commit -m "feat(assessments): record respondent_mode (staff/child) on assessments"
```

---

## Task 2: The `RespondentSurvey` component

**Files:** Create `frontend/src/components/RespondentSurvey.jsx`.

- [ ] **Step 1: Create the component**

Create `frontend/src/components/RespondentSurvey.jsx`:
```jsx
import React, { useState } from 'react';
import { Button, Icon } from '../ui';

const FACES = ['😞', '😕', '😐', '🙂', '😄'];

export default function RespondentSurvey({ questions, childName = '', initial = {}, onComplete, onExit }) {
  const [idx, setIdx] = useState(0);
  const [answers, setAnswers] = useState(initial || {});

  const total = questions.length;
  const done = idx >= total;
  const q = questions[idx];
  const firstName = (childName || '').split(' ')[0];

  const choose = (val) => {
    setAnswers((a) => ({ ...a, [q.id]: val }));
    setTimeout(() => setIdx((i) => i + 1), 220);
  };
  const back = () => setIdx((i) => Math.max(0, i - 1));

  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 100, background: 'linear-gradient(160deg, var(--blue-50), var(--surface))', display: 'flex', flexDirection: 'column', animation: 'racco-fade-in var(--dur-base) var(--ease-out)' }}>
      <button onClick={onExit} title="Exit" aria-label="Exit survey" style={{ position: 'absolute', top: 16, right: 16, background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--text-faint)', fontSize: 12, display: 'inline-flex', alignItems: 'center', gap: 5 }}>
        <Icon name="x" size={16} /> Exit
      </button>

      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: 24, textAlign: 'center', maxWidth: 720, margin: '0 auto', width: '100%' }}>
        {done ? (
          <div style={{ animation: 'racco-pop-in var(--dur-base) var(--ease-out)' }}>
            <div style={{ fontSize: 64 }}>🎉</div>
            <h1 style={{ fontFamily: 'var(--font-display)', fontSize: 30, fontWeight: 800, color: 'var(--blue-700)', margin: '10px 0' }}>All done!</h1>
            <p style={{ fontSize: 17, color: 'var(--text-muted)', marginBottom: 26 }}>Thank you{firstName ? `, ${firstName}` : ''}! You answered every question. 🌟</p>
            <Button variant="primary" onClick={() => onComplete(answers)} iconRight={<Icon name="arrow-right" size={18} />}>Finish</Button>
          </div>
        ) : (
          <>
            {idx === 0 && <p style={{ fontSize: 18, color: 'var(--text-muted)', marginBottom: 8 }}>Hi {firstName || 'there'}! 👋 Let's answer some questions together.</p>}
            <div style={{ display: 'flex', gap: 7, marginBottom: 22 }}>
              {questions.map((_, i) => (
                <span key={i} style={{ width: 10, height: 10, borderRadius: '50%', background: i < idx ? 'var(--success-500)' : i === idx ? 'var(--blue-600)' : 'var(--ink-200)', transition: 'var(--transition-base)' }} />
              ))}
            </div>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 13, color: 'var(--text-faint)', marginBottom: 10 }}>Question {idx + 1} of {total}</div>
            <h1 style={{ fontFamily: 'var(--font-display)', fontSize: 26, fontWeight: 800, color: 'var(--text-strong)', lineHeight: 1.3, marginBottom: 30, maxWidth: 620 }}>{q.question_text}</h1>
            <Choices question={q} value={answers[q.id]} onChoose={choose} />
            {idx > 0 && <button onClick={back} style={{ marginTop: 28, background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', fontSize: 14, fontWeight: 700, display: 'inline-flex', alignItems: 'center', gap: 6 }}><Icon name="arrow-left" size={16} /> Back</button>}
          </>
        )}
      </div>
    </div>
  );
}

function Choices({ question, value, onChoose }) {
  const type = question.question_type;
  const big = (on) => ({ cursor: 'pointer', borderRadius: 'var(--radius-xl)', border: `2.5px solid ${on ? 'var(--blue-600)' : 'var(--border-strong)'}`, background: on ? 'var(--blue-50)' : 'var(--surface)', transition: 'var(--transition-base)', boxShadow: on ? 'var(--shadow-brand)' : 'var(--shadow-xs)' });

  if (type === 'rating_scale') {
    return (
      <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', justifyContent: 'center' }}>
        {FACES.map((face, i) => {
          const n = String(i + 1); const on = value === n;
          return (
            <button key={n} onClick={() => onChoose(n)} style={{ ...big(on), width: 92, height: 104, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 4 }}>
              <span style={{ fontSize: 40, transform: on ? 'scale(1.12)' : 'none', transition: 'var(--transition-base)' }}>{face}</span>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 13, fontWeight: 700, color: on ? 'var(--blue-700)' : 'var(--text-faint)' }}>{n}</span>
            </button>
          );
        })}
      </div>
    );
  }

  const opts = type === 'yes_no' ? [['👍', 'Yes'], ['👎', 'No']] : (question.options || []).map((o) => [null, o]);
  if (opts.length === 0) {
    return <TextChoice value={value} onChoose={onChoose} />;
  }
  const wide = type === 'yes_no';
  return (
    <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', justifyContent: 'center', maxWidth: 560 }}>
      {opts.map(([emoji, label]) => {
        const on = value === label;
        return (
          <button key={label} onClick={() => onChoose(label)} style={{ ...big(on), padding: wide ? '20px 36px' : '16px 24px', minWidth: wide ? 150 : 200, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10, fontFamily: 'var(--font-sans)', fontWeight: 700, fontSize: 19, color: on ? 'var(--blue-700)' : 'var(--text-strong)' }}>
            {emoji && <span style={{ fontSize: 30 }}>{emoji}</span>}{label}
          </button>
        );
      })}
    </div>
  );
}

function TextChoice({ value, onChoose }) {
  const [txt, setTxt] = useState(value || '');
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 14 }}>
      <input value={txt} onChange={(e) => setTxt(e.target.value)} placeholder="Type your answer" style={{ width: '100%', maxWidth: 460, padding: '14px 16px', borderRadius: 'var(--radius-lg)', border: '2px solid var(--border-strong)', fontSize: 18, textAlign: 'center' }} />
      <Button variant="primary" onClick={() => onChoose(txt)} disabled={!txt.trim()} iconRight={<Icon name="arrow-right" size={16} />}>Next</Button>
    </div>
  );
}
```

- [ ] **Step 2: Verify the build**

Run (from `frontend/`): `npm run build`
Expected: built, no errors.

- [ ] **Step 3: Commit (deferred — checkpoint only)**

```bash
git add frontend/src/components/RespondentSurvey.jsx
git commit -m "feat(respondent): child-friendly standalone survey component"
```

---

## Task 3: Kiosk handoff in the wizard

**Files:** Modify `frontend/src/pages/Assessment.jsx`.

- [ ] **Step 1: Import the component**

In `frontend/src/pages/Assessment.jsx`, add the import after the `ui` import:
```jsx
import RespondentSurvey from '../components/RespondentSurvey';
```

- [ ] **Step 2: Add kiosk + respondent-mode state**

After the existing `const [error, setError] = useState('');` line, add:
```jsx
  const [kiosk, setKiosk] = useState(false);
  const [respondentMode, setRespondentMode] = useState('staff');
```

- [ ] **Step 3: Send `respondent_mode` and reset it on success**

In `submit`, add `respondent_mode: respondentMode,` to the POST body (after the `notes,` line):
```jsx
        notes,
        respondent_mode: respondentMode,
        responses: questions.map((q) => ({ question: q.id, answer: String(answers[q.id]) })),
```
And in the success `setTimeout` reset, add `setRespondentMode('staff');`:
```jsx
      setTimeout(() => {
        setSent(false); setStep(1); setChild(''); setFormId(''); setAnswers({}); setNotes(''); setRespondentMode('staff');
      }, 2600);
```

- [ ] **Step 4: Add the "Hand to child" button on step 3**

In `Assessment.jsx`, replace the step-3 heading block:
```jsx
          {step === 3 && (
            <div>
              <h2 style={{ fontFamily: 'var(--font-display)', fontSize: 19, fontWeight: 700, marginBottom: 4 }}>{form?.title || 'Questionnaire'}</h2>
              <p style={{ fontSize: 13.5, color: 'var(--text-muted)', marginBottom: 18 }}>Answer each item based on the session.</p>
```
with (adds a flex header + the kiosk button):
```jsx
          {step === 3 && (
            <div>
              <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12, marginBottom: 18 }}>
                <div>
                  <h2 style={{ fontFamily: 'var(--font-display)', fontSize: 19, fontWeight: 700, marginBottom: 4 }}>{form?.title || 'Questionnaire'}</h2>
                  <p style={{ fontSize: 13.5, color: 'var(--text-muted)' }}>Answer each item based on the session, or hand the device to the child.</p>
                </div>
                <Button variant="secondary" onClick={() => setKiosk(true)} iconLeft={<Icon name="smile" size={17} />}>Hand to child</Button>
              </div>
```

- [ ] **Step 5: Render the kiosk overlay**

In `Assessment.jsx`, add the overlay just before the final closing `</div>` of the component's returned tree (right after the closing `</Card>`'s wrapping `</div>`, before the outermost `</div>`). Concretely, find:
```jsx
        </Card>
      </div>
    </div>
  );
}
```
and replace it with:
```jsx
        </Card>
      </div>
      {kiosk && (
        <RespondentSurvey
          questions={questions}
          childName={childObj?.fullname}
          initial={answers}
          onComplete={(a) => { setAnswers(a); setRespondentMode('child'); setKiosk(false); setStep(4); }}
          onExit={() => setKiosk(false)}
        />
      )}
    </div>
  );
}
```

- [ ] **Step 6: Verify the build**

Run (from `frontend/`): `npm run build`
Expected: built, no errors.

- [ ] **Step 7: Commit (deferred — checkpoint only)**

```bash
git add frontend/src/pages/Assessment.jsx
git commit -m "feat(assessment): kiosk handoff to child respondent survey"
```

---

## Task 4: End-to-end verification

- [ ] **Step 1: Apply migration + full backend suite**

Run (from `backend/`): `./venv/Scripts/python.exe manage.py migrate`, then `./venv/Scripts/python.exe manage.py test`
Expected: all OK.

- [ ] **Step 2: Frontend build**

Run (from `frontend/`): `npm run build`
Expected: built, no errors.

- [ ] **Step 3: Browser smoke test (preview)**

Start backend (`runserver`) + preview, log in as the test Psychologist (`psy@racco1.gov.ph` / `psy12345`), ensure an active questionnaire exists, open **Assessment Tools**:
- Select a child → pick the questionnaire → on **Responses**, click **Hand to child**.
- The full-screen child survey appears (faces for ratings, big Yes/No, one question at a time). Answer through to "All done! 🎉" → **Finish**.
- Control returns to **Review & Sign**; add notes → **Sign & Submit**.
- Verify the saved assessment has `respondent_mode="child"` (via `GET /api/assessments/` or the shell).
```
