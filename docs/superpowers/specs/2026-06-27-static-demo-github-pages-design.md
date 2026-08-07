# Static Demo on GitHub Pages — Design

- **Date:** 2026-06-27
- **Status:** Approved (design)
- **Type:** Additive — a no-backend "demo mode" build of the existing frontend, deployed to GitHub Pages for mobile/offline presentation. Does not change the real app's behavior.

---

## 1. Goal

A **single, always-on, shareable URL** (`https://23150056-beep.github.io/NACC_RACCO1_SYS/`) that runs the full RACCO I UI on any phone/browser **with no backend, no accounts, and no cost** — for presenting the system. Data is mocked in-browser; the real Django-backed app is unaffected.

## 2. Approach — one flag, two builds

A build-time flag **`VITE_DEMO_MODE`** (Vite env). When `'true'`:
- the axios `api` client's **adapter** is swapped for an in-browser **mock backend** (no network),
- the app uses **HashRouter** and a Pages **base path**.

When unset (normal `npm run dev` / `npm run build`), nothing changes — real backend, `BrowserRouter`, root base. The app's feature code (`Children.jsx`, `Assessment.jsx`, etc.) is **untouched** — it keeps calling `api.get('/children/')`; only where those calls land differs.

## 3. Mock backend (`src/api/mockBackend.js`)

A module exporting `mockAdapter(config)` (an axios adapter) backed by a `store` object that is **seeded on first load and persisted to `localStorage`** (key `nacc_demo_db`), so adds/edits/archives stick per device.

**Adapter behavior:** parse `config.method` + `config.url` (relative path, e.g. `/children/`) + `config.data` (JSON.parse for writes; FormData passes through). Match against a route table; return `Promise.resolve({ data, status, statusText, headers: {}, config })`. Unmatched → resolve `{ status: 404 }` so callers' `.catch` paths behave.

**Endpoints implemented** (every call the app makes — see grep inventory):
| Method + path | Behavior |
|---|---|
| `POST /auth/login/` | match email in demo users (any password); return `{ access: "demo.<id>", refresh: "demo", user }` |
| `GET /auth/me/` | decode `<id>` from the bearer token in `config.headers.Authorization`; return that user |
| `GET /users/`, `POST/PUT /users/...`, `POST /users/:id/archive/` | CRUD over demo users (archive = soft hide) |
| `GET /roles/` | the 3 roles |
| `GET /children/`, `GET /guardians/`, create/edit/`archive` | CRUD over demo children/guardians |
| `GET /questionnaires/`, `GET /questionnaires/:id/`, create/edit/`archive` | CRUD over demo questionnaires (nested questions) |
| `GET /active-questionnaires/` | questionnaires with `status==="active"` |
| `POST /questionnaires/extract/` | ignore the file; after ~600 ms return a **canned sample draft** (4 questions) |
| `POST /assessments/` | create an assessment (+ responses), push an activity entry; return it |
| `GET /activity/` | the activity feed (newest first, capped 50) |

**Activity logging in the mock:** create/edit/archive on children/questionnaires/users + login push an entry into the activity store, so the bell + dashboard feed update live from the presenter's actions — exactly like the real backend.

**Seed data:** 3 roles; demo users — `admin@racco1.gov.ph` (Administrator), `psy@racco1.gov.ph` (Psychologist), `staff@racco1.gov.ph` (Staff); ~6 children with guardians; 2 **active** questionnaires (one with rating + yes/no + emotion questions so the kiosk shows variety); a few seed activity entries.

A `resetDemo()` helper (clears `localStorage` key) is exposed for re-seeding during a demo.

## 4. Adapter wiring (`src/api/client.js`)

After creating `api`, add:
```js
if (import.meta.env.VITE_DEMO_MODE === 'true') {
  api.defaults.adapter = mockAdapter;   // imported from ./mockBackend
}
```
The existing JWT request interceptor still runs (harmless); the 401-refresh response interceptor never triggers because the mock never 401s.

## 5. Demo-friendly login (`Login.jsx`)

In demo mode only (`import.meta.env.VITE_DEMO_MODE === 'true'`), render a row of **one-tap buttons** under the form — **"Enter as Admin / Psychologist / Staff"** — each calling the existing `login(email, password)` with that demo account. The normal typed form still works. No code path changes when the flag is off.

## 6. GitHub Pages build (`vite.config.js`, `App.jsx`)

- **`vite.config.js`:** `base: process.env.VITE_DEMO_MODE === 'true' ? '/NACC_RACCO1_SYS/' : '/'` (read from the build env).
- **`App.jsx`:** `const Router = import.meta.env.VITE_DEMO_MODE === 'true' ? HashRouter : BrowserRouter;` and use `<Router>`. HashRouter (`…/#/path`) makes deep links + refresh work on Pages with zero server config.

## 7. Deployment (`.github/workflows/deploy-demo.yml`)

A GitHub Actions workflow, on push to `main` (and manual `workflow_dispatch`):
1. checkout → setup Node → `npm ci` in `frontend/` → `npm run build` with `VITE_DEMO_MODE=true`.
2. `actions/configure-pages` → `actions/upload-pages-artifact` (`frontend/dist`) → `actions/deploy-pages`.

Permissions: `pages: write`, `id-token: write`. **One manual step for the user:** repo **Settings → Pages → Source = "GitHub Actions"** (a repo setting I cannot change). After that, every push to `main` redeploys; live ~2–3 min later.

## 8. Honesty touches

- A small fixed **"DEMO"** badge (corner pill) rendered only in demo mode, so viewers know it's a demonstration on sample data.
- The canned `/extract/` result and the per-device localStorage data are demo conveniences, clearly not real OCR / not shared storage.

## 9. Verification

- Local: `VITE_DEMO_MODE=true npm run dev` → log in via a one-tap button with **no backend running**; exercise children CRUD, questionnaire build, run an assessment + kiosk, watch the bell update. Then `npm run build` in demo mode succeeds.
- Post-deploy: open the Pages URL on desktop + phone; confirm one-tap login, navigation (hash routes), and a create/▶ flow work.

## 10. File change summary

**New:** `frontend/src/api/mockBackend.js`, `.github/workflows/deploy-demo.yml`.
**Modify:** `frontend/src/api/client.js` (conditional adapter), `frontend/src/App.jsx` (conditional Router), `frontend/src/pages/Login.jsx` (demo quick-login buttons + DEMO badge or a small `DemoBadge` in `App`), `frontend/vite.config.js` (base path). No change to any feature page's logic.
