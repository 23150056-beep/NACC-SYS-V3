# Static Demo on GitHub Pages — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A no-backend "demo mode" build of the frontend, deployed to GitHub Pages, usable on any phone/browser for presenting.

**Architecture:** A `VITE_DEMO_MODE` flag swaps the axios adapter for an in-browser, localStorage-backed mock backend, switches to HashRouter + a Pages base path, and adds one-tap role login. A GitHub Actions workflow builds + deploys to Pages. The real app is unchanged when the flag is off.

**Tech Stack:** React + Vite; axios custom adapter; GitHub Actions + Pages.

**Spec:** [2026-06-27-static-demo-github-pages-design.md](../specs/2026-06-27-static-demo-github-pages-design.md)

**Conventions:** Frontend from `frontend/`. Commits omit any Claude co-author trailer. Commits deferred until the user asks (checkpoints below).

---

## Task 1: The in-browser mock backend

**Files:** Create `frontend/src/api/mockBackend.js`; Modify `frontend/src/api/client.js`.

- [ ] **Step 1: Create the mock backend**

Create `frontend/src/api/mockBackend.js`:
```js
// In-browser mock of the Django API for the static GitHub Pages demo.
// Activated only when VITE_DEMO_MODE === 'true' (see api/client.js).
const KEY = 'nacc_demo_db';

const mkUser = (id, email, first, last, role, role_name) => ({
  id, email, username: email.split('@')[0], first_name: first, last_name: last,
  middle_initial: '', contact_details: '', role, role_name,
  fullname: `${first} ${last}`, status: 'active',
});
const q = (id, text, type, options = [], order = 1) => ({ id, question_text: text, question_type: type, options, order });

function seed() {
  const roles = [
    { id: 1, role_name: 'Administrator' },
    { id: 2, role_name: 'Psychologist' },
    { id: 3, role_name: 'Staff' },
  ];
  const users = [
    mkUser(1, 'admin@racco1.gov.ph', 'System', 'Administrator', 1, 'Administrator'),
    mkUser(2, 'psy@racco1.gov.ph', 'Maria', 'Cruz', 2, 'Psychologist'),
    mkUser(3, 'staff@racco1.gov.ph', 'Jose', 'Ramos', 3, 'Staff'),
  ];
  const guardians = [
    { id: 11, fullname: 'Rosario Dela Cruz', gender: 'Female', case_type: 'Foster Care', status: 'active', birth_date: '', address: 'Bauang, La Union' },
    { id: 12, fullname: 'Teresita Mendoza', gender: 'Female', case_type: 'Kinship Care', status: 'active', birth_date: '', address: 'San Fernando, La Union' },
    { id: 13, fullname: 'Elena Aquino', gender: 'Female', case_type: 'Foster Care', status: 'active', birth_date: '', address: 'Agoo, La Union' },
  ];
  const child = (id, fullname, gender, case_type, guardian, birth_date) => ({ id, fullname, gender, case_type, guardian, status: 'active', birth_date, address: 'La Union' });
  const children = [
    child(21, 'Andres B. Lopez', 'Male', 'Residential', null, '2014-03-02'),
    child(22, 'Gabriel T. Mendoza', 'Male', 'Kinship Care', 12, '2016-07-11'),
    child(23, 'Juan Miguel Dela Cruz', 'Male', 'Foster Care', 11, '2016-01-20'),
    child(24, 'Maria Clara Santos', 'Female', 'Adoption', null, '2019-05-09'),
    child(25, 'Paolo Pasco', 'Male', 'Foster Care', null, '2003-11-01'),
    child(26, 'Sofia Reyes Aquino', 'Female', 'Foster Care', 13, '2019-02-14'),
  ];
  const questionnaires = [
    { id: 31, title: 'Child Wellbeing Check', age_group: '5-8', description: 'General wellbeing screen.', status: 'active', questions: [
      q(101, 'The child is calm during sessions.', 'rating_scale', [], 1),
      q(102, 'Does the child sleep well?', 'yes_no', [], 2),
      q(103, 'The child interacts with peers.', 'rating_scale', [], 3),
    ] },
    { id: 32, title: 'Emotional Check-in', age_group: '5-8', description: 'How the child feels.', status: 'active', questions: [
      q(111, 'How are you feeling today?', 'rating_scale', [], 1),
      q(112, 'Which best describes your mood?', 'emotion', ['Happy', 'Sad', 'Scared', 'Angry', 'Calm'], 2),
      q(113, 'Did you feel safe this week?', 'yes_no', [], 3),
    ] },
  ];
  const activity = [
    { id: 41, actor_label: 'System Administrator', action: 'created', category: 'user', entity_type: 'User', entity_label: 'Maria Cruz', entity_id: 2, created_at: new Date(Date.now() - 3600e3).toISOString() },
    { id: 42, actor_label: 'Maria Cruz', action: 'login', category: 'security', entity_type: '', entity_label: '', entity_id: null, created_at: new Date(Date.now() - 1800e3).toISOString() },
  ];
  return { seq: 1000, roles, users, guardians, children, questionnaires, assessments: [], activity };
}

let db = load();
function load() {
  try { const s = localStorage.getItem(KEY); if (s) return JSON.parse(s); } catch (e) { /* reseed */ }
  const d = seed();
  localStorage.setItem(KEY, JSON.stringify(d));
  return d;
}
function save() { localStorage.setItem(KEY, JSON.stringify(db)); }
function nextId() { db.seq += 1; return db.seq; }
export function resetDemo() { localStorage.removeItem(KEY); db = load(); }

let actor = null;
function userFromConfig(config) {
  const auth = config.headers?.Authorization || config.headers?.common?.Authorization || '';
  const m = /demo\.(\d+)/.exec(auth);
  return m ? db.users.find((u) => u.id === Number(m[1])) : null;
}
function logActivity(action, category, entity_type, entity_label, entity_id) {
  db.activity.unshift({
    id: nextId(), actor_label: actor?.fullname || 'System', action, category,
    entity_type, entity_label: entity_label || '', entity_id: entity_id ?? null,
    created_at: new Date().toISOString(),
  });
}

const ok = (data, status = 200) => ({ data, status });
const childOut = (c) => ({ ...c, guardian_name: db.guardians.find((g) => g.id === c.guardian)?.fullname || null });

function handle(method, url, body, config) {
  const id = (re) => { const m = re.exec(url); return m ? Number(m[1]) : null; };

  // --- auth ---
  if (url === '/auth/login/' && method === 'post') {
    const u = db.users.find((x) => x.email === body.email && x.status === 'active');
    if (!u) return ok({ detail: 'No active account found with the given credentials.' }, 401);
    actor = u; logActivity('login', 'security', '', '', null); save();
    return ok({ access: `demo.${u.id}`, refresh: 'demo', user: u });
  }
  if (url === '/auth/me/' && method === 'get') return actor ? ok(actor) : ok({ detail: 'Unauthorized' }, 401);

  // --- roles / users ---
  if (url === '/roles/') return ok(db.roles);
  if (url === '/users/' && method === 'get') return ok(db.users.filter((u) => u.status !== 'archived'));
  if (url === '/users/' && method === 'post') {
    const u = mkUser(nextId(), body.email, body.first_name || '', body.last_name || '', Number(body.role) || null, db.roles.find((r) => r.id === Number(body.role))?.role_name);
    Object.assign(u, { username: body.username || u.username, middle_initial: body.middle_initial || '', contact_details: body.contact_details || '' });
    db.users.push(u); logActivity('created', 'user', 'User', u.fullname || u.email, u.id); save();
    return ok(u, 201);
  }
  if (/^\/users\/(\d+)\/$/.test(url) && method === 'put') {
    const u = db.users.find((x) => x.id === id(/^\/users\/(\d+)\//));
    if (u) { Object.assign(u, body, { role: Number(body.role) || u.role, role_name: db.roles.find((r) => r.id === Number(body.role))?.role_name || u.role_name }); u.fullname = `${u.first_name} ${u.last_name}`.trim(); logActivity('updated', 'user', 'User', u.fullname, u.id); save(); }
    return ok(u);
  }
  if (/^\/users\/(\d+)\/archive\/$/.test(url)) {
    const u = db.users.find((x) => x.id === id(/^\/users\/(\d+)\//));
    if (u) { u.status = 'archived'; logActivity('archived', 'user', 'User', u.fullname, u.id); save(); }
    return ok({ status: 'archived' });
  }

  // --- children / guardians ---
  if (url === '/guardians/' && method === 'get') return ok(db.guardians.filter((g) => g.status !== 'archived'));
  if (url === '/children/' && method === 'get') return ok(db.children.filter((c) => c.status !== 'archived').map(childOut));
  if (url === '/children/' && method === 'post') {
    const c = { id: nextId(), status: 'active', ...body, guardian: body.guardian || null };
    db.children.push(c); logActivity('created', 'record', 'Child', c.fullname, c.id); save();
    return ok(childOut(c), 201);
  }
  if (/^\/children\/(\d+)\/$/.test(url) && method === 'put') {
    const c = db.children.find((x) => x.id === id(/^\/children\/(\d+)\//));
    if (c) { Object.assign(c, body, { guardian: body.guardian || null }); logActivity('updated', 'record', 'Child', c.fullname, c.id); save(); }
    return ok(childOut(c));
  }
  if (/^\/children\/(\d+)\/archive\/$/.test(url)) {
    const c = db.children.find((x) => x.id === id(/^\/children\/(\d+)\//));
    if (c) { c.status = 'archived'; logActivity('archived', 'record', 'Child', c.fullname, c.id); save(); }
    return ok({ status: 'archived' });
  }

  // --- questionnaires ---
  if (url === '/questionnaires/' && method === 'get') return ok(db.questionnaires.filter((x) => x.status !== 'archived'));
  if (url === '/active-questionnaires/') return ok(db.questionnaires.filter((x) => x.status === 'active'));
  if (url === '/questionnaires/extract/' && method === 'post') {
    return ok({ title: 'Behavioral Adjustment Checklist', age_group: '', questions: [
      { question_text: 'The child shows signs of distress.', question_type: 'rating_scale', options: [], order: 1 },
      { question_text: 'Does the child have trouble sleeping?', question_type: 'yes_no', options: [], order: 2 },
      { question_text: 'The child avoids talking about home.', question_type: 'rating_scale', options: [], order: 3 },
      { question_text: 'The child interacts well with peers.', question_type: 'rating_scale', options: [], order: 4 },
    ] });
  }
  if (/^\/questionnaires\/(\d+)\/$/.test(url) && method === 'get') return ok(db.questionnaires.find((x) => x.id === id(/^\/questionnaires\/(\d+)\//)));
  const writeQuestions = (qs) => (qs || []).map((qq, i) => ({ id: nextId(), question_text: qq.question_text, question_type: qq.question_type, options: qq.options || [], order: qq.order || i + 1 }));
  if (url === '/questionnaires/' && method === 'post') {
    const item = { id: nextId(), title: body.title, age_group: body.age_group || '', description: body.description || '', status: body.status || 'draft', questions: writeQuestions(body.questions) };
    db.questionnaires.unshift(item); logActivity('created', 'record', 'Questionnaire', item.title, item.id); save();
    return ok(item, 201);
  }
  if (/^\/questionnaires\/(\d+)\/$/.test(url) && method === 'put') {
    const item = db.questionnaires.find((x) => x.id === id(/^\/questionnaires\/(\d+)\//));
    if (item) { Object.assign(item, { title: body.title, age_group: body.age_group || '', description: body.description || '', status: body.status || item.status, questions: writeQuestions(body.questions) }); logActivity('updated', 'record', 'Questionnaire', item.title, item.id); save(); }
    return ok(item);
  }
  if (/^\/questionnaires\/(\d+)\/archive\/$/.test(url)) {
    const item = db.questionnaires.find((x) => x.id === id(/^\/questionnaires\/(\d+)\//));
    if (item) { item.status = 'archived'; logActivity('archived', 'record', 'Questionnaire', item.title, item.id); save(); }
    return ok({ status: 'archived' });
  }

  // --- assessments / activity ---
  if (url === '/assessments/' && method === 'post') {
    const a = { id: nextId(), ...body, psychologist: actor?.id, status: 'completed', assessment_date: new Date().toISOString().slice(0, 10) };
    db.assessments.push(a);
    logActivity('created', 'record', 'Assessment', db.children.find((c) => c.id === Number(body.child))?.fullname || 'child', a.id);
    save();
    return ok(a, 201);
  }
  if (url.startsWith('/activity/') && method === 'get') {
    const cat = config.params?.category;
    let list = db.activity;
    if (cat) list = list.filter((e) => e.category === cat);
    return ok(list.slice(0, 50));
  }

  return ok({ detail: 'Not found (demo)' }, 404);
}

export function mockAdapter(config) {
  actor = userFromConfig(config) || actor;
  const method = (config.method || 'get').toLowerCase();
  const url = (config.url || '').split('?')[0];
  let body = {};
  if (config.data && typeof config.data === 'string') { try { body = JSON.parse(config.data); } catch (e) { body = {}; } }
  const wait = url === '/questionnaires/extract/' ? 600 : 120;
  return new Promise((resolve) => {
    setTimeout(() => {
      const r = handle(method, url, body, config);
      resolve({ data: r.data, status: r.status, statusText: 'OK', headers: {}, config, request: {} });
    }, wait);
  });
}
```

- [ ] **Step 2: Wire the adapter in the client**

In `frontend/src/api/client.js`, add the import at the top and the conditional after `const api = axios.create({ baseURL });`:
```js
import { mockAdapter } from './mockBackend';
```
```js
const api = axios.create({ baseURL });

if (import.meta.env.VITE_DEMO_MODE === 'true') {
  api.defaults.adapter = mockAdapter;
}
```

- [ ] **Step 3: Commit (deferred — checkpoint only)**

```bash
git add frontend/src/api/mockBackend.js frontend/src/api/client.js
git commit -m "feat(demo): in-browser mock backend for the static demo build"
```

---

## Task 2: Demo wiring — Router, base path, login buttons, badge

**Files:** Modify `frontend/src/App.jsx`, `frontend/vite.config.js`, `frontend/src/pages/Login.jsx`.

- [ ] **Step 1: Conditional Router + DEMO badge in `App.jsx`**

In `frontend/src/App.jsx`, change the router import line:
```jsx
import { BrowserRouter, HashRouter, Routes, Route } from 'react-router-dom';
```
Add, just before `export default function App() {`:
```jsx
const DEMO = import.meta.env.VITE_DEMO_MODE === 'true';
const Router = DEMO ? HashRouter : BrowserRouter;

function DemoBadge() {
  if (!DEMO) return null;
  return (
    <div style={{ position: 'fixed', bottom: 12, left: 12, zIndex: 200, background: 'var(--blue-600)', color: '#fff', fontFamily: 'var(--font-sans)', fontWeight: 800, fontSize: 11, letterSpacing: '0.06em', padding: '5px 11px', borderRadius: 'var(--radius-pill)', boxShadow: 'var(--shadow-md)', pointerEvents: 'none' }}>DEMO · SAMPLE DATA</div>
  );
}
```
Replace `<BrowserRouter>` with `<Router>` and `</BrowserRouter>` with `</Router>`, and add `<DemoBadge />` just inside `<ActivityProvider>` (before `<Router>`):
```jsx
    <AuthProvider>
      <ActivityProvider>
        <DemoBadge />
        <Router>
          <Routes>
            {/* ...unchanged routes... */}
          </Routes>
        </Router>
      </ActivityProvider>
    </AuthProvider>
```

- [ ] **Step 2: Pages base path in `vite.config.js`**

Replace `frontend/vite.config.js` with:
```js
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  base: process.env.VITE_DEMO_MODE === 'true' ? '/NACC_RACCO1_SYS/' : '/',
  plugins: [react()],
})
```

- [ ] **Step 3: One-tap demo login in `Login.jsx`**

In `frontend/src/pages/Login.jsx`, find the submit button (`Enter Workspace`). Immediately AFTER the closing tag of the `<form>` that wraps the email/password (i.e., after the form's submit button block), add a demo-only quick-login row. First, ensure the component can call `login` for preset accounts — it already uses `login` from `useAuth()` (it must, since the form logs in). Add this block where the form's children end, before the closing `</form>` or right after it inside the same card:
```jsx
            {import.meta.env.VITE_DEMO_MODE === 'true' && (
              <div style={{ marginTop: 16 }}>
                <div style={{ textAlign: 'center', fontSize: 11, color: 'var(--text-faint)', fontWeight: 700, letterSpacing: '0.04em', marginBottom: 8 }}>DEMO — TAP A ROLE TO ENTER</div>
                <div style={{ display: 'flex', gap: 8 }}>
                  {[['Admin', 'admin@racco1.gov.ph'], ['Psychologist', 'psy@racco1.gov.ph'], ['Staff', 'staff@racco1.gov.ph']].map(([label, email]) => (
                    <button key={email} type="button" onClick={() => login(email, 'demo').then(() => navigate('/')).catch(() => {})}
                      style={{ flex: 1, padding: '9px 6px', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-strong)', background: 'var(--surface)', color: 'var(--text-strong)', fontFamily: 'var(--font-sans)', fontWeight: 700, fontSize: 12.5, cursor: 'pointer' }}>{label}</button>
                  ))}
                </div>
              </div>
            )}
```
NOTE: confirm `Login.jsx` already destructures `login` from `useAuth()` and `navigate` from `useNavigate()`. If it uses different names (e.g., the submit handler), reuse those exact handles; do not invent new ones. (The mock accepts any password, so `'demo'` works.)

- [ ] **Step 4: Commit (deferred — checkpoint only)**

```bash
git add frontend/src/App.jsx frontend/vite.config.js frontend/src/pages/Login.jsx
git commit -m "feat(demo): hash router, base path, demo badge, one-tap login"
```

---

## Task 3: GitHub Actions deploy workflow

**Files:** Create `.github/workflows/deploy-demo.yml`.

- [ ] **Step 1: Create the workflow**

Create `.github/workflows/deploy-demo.yml`:
```yaml
name: Deploy demo to GitHub Pages

on:
  push:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: read
  pages: write
  id-token: write

concurrency:
  group: pages
  cancel-in-progress: true

jobs:
  build:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: frontend
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: npm
          cache-dependency-path: frontend/package-lock.json
      - run: npm ci
      - run: npm run build
        env:
          VITE_DEMO_MODE: 'true'
      - uses: actions/configure-pages@v5
      - uses: actions/upload-pages-artifact@v3
        with:
          path: frontend/dist

  deploy:
    needs: build
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - id: deployment
        uses: actions/deploy-pages@v4
```

- [ ] **Step 2: Commit (deferred — checkpoint only)**

```bash
git add .github/workflows/deploy-demo.yml
git commit -m "ci(demo): GitHub Pages deploy workflow"
```

---

## Task 4: Local verification (no backend)

- [ ] **Step 1: Enable demo mode locally without polluting normal dev**

Create `frontend/.env.local` (gitignored by Vite's default `*.local`) with:
```
VITE_DEMO_MODE=true
```

- [ ] **Step 2: Stop any backend, run the demo, drive it**

Stop the Django server (free :8000) so the demo proves it needs no backend. Start the frontend (it picks up `.env.local`). In the browser:
- The login screen shows the **one-tap role buttons** + a **DEMO** badge.
- Tap **Psychologist** → dashboard loads (mock data), bell shows activity.
- Children Records → add a child → it appears (persisted to localStorage); the bell logs it.
- Assessment Instruments → "Digitize from paper" → upload any file → a canned 4-question draft opens → publish.
- Assessment Tools → run an assessment, including **Hand to child** kiosk → submit.
- Reload the page → still logged in, data persisted.

- [ ] **Step 3: Demo production build succeeds**

Run (from `frontend/`, PowerShell): `$env:VITE_DEMO_MODE='true'; npm run build`
Expected: built; `dist/index.html` references assets under `/NACC_RACCO1_SYS/`.
Then unset: `Remove-Item Env:VITE_DEMO_MODE`.

- [ ] **Step 4: Remove the local override**

Delete `frontend/.env.local` (so normal `npm run dev` stays real-backend).

- [ ] **Step 5: Verify normal build is unaffected**

Run (from `frontend/`): `npm run build`
Expected: built with root base `/` and BrowserRouter (no demo behavior).

---

## Task 5: Ship + enable Pages

- [ ] **Step 1: Commit everything (when the user approves) and push to main**

```bash
git add -A
git commit -m "feat(demo): static GitHub Pages demo (mock backend + deploy workflow)"
git push origin main
```

- [ ] **Step 2: User enables Pages (one-time, manual)**

Tell the user: GitHub → repo **Settings → Pages → Build and deployment → Source: "GitHub Actions"**. Then the `Deploy demo` workflow (already triggered by the push) publishes the site; the live URL is `https://23150056-beep.github.io/NACC_RACCO1_SYS/`. Re-run the workflow from the Actions tab if it ran before Pages was enabled.
