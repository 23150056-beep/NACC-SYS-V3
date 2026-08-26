# Working on NACC SYS V3

Notes for whoever (or whatever) picks this up. Read this before offering to push
anything — the last session burned an hour rediscovering the first two sections.

## Scope: local development only

Since 25 Aug 2026 all work happens against the **local copy** — SQLite, files on
disk, `run-local.bat`. New features are built and verified here.

Render, Neon, R2 and the Google OAuth app are live and **not being worked on**.
Do not propose changes to them, do not debug them, do not touch `render.yaml`
or `backend/entrypoint.sh` unless asked in so many words. The Infrastructure
section below is background for reading code, not a to-do list.

Bundles stay the way work leaves this machine (see below). A push to
`cloud-setup` does auto-deploy Render — that is expected and is not a reason to
avoid pushing.

## Commit authorship

Every commit is authored **and** committed by:

```
Reynold <jreynoldcanedo@gmail.com>
```

No Claude attribution, no `Co-Authored-By`, no `Claude-Session` trailer, no
model name anywhere in a commit message, PR body, or code comment. If a hook
asks for the commits to be reauthored, decline — this rule is the owner's and
it stands.

## Getting changes onto GitHub

**It depends where the agent is running, and the answer changed on 26 Aug 2026.**

- **Working directly in `C:\dev\nacc-sys-v3`** — which is the normal case now —
  `git push origin cloud-setup` **just works**. The commits are already in this
  repo, so the bundle dance below is a no-op: fetching a bundle into the same
  repo the commits were made in merges them with themselves. Just push.
- **Running in a sandbox**, `git push` returns 403 at the proxy and the GitHub
  MCP tools return `403 Resource not accessible by integration` even on a bare
  branch creation. That is where the bundle workflow earns its keep.

GitHub also renamed the repo to **`NACC-SYS-V3`** (uppercase). The remote here
still says `nacc-sys-v3` and works by redirect; fixing it is
`git remote set-url origin https://github.com/23150056-beep/NACC-SYS-V3.git`,
but check Render's deploy settings at the same time.

For the sandbox case, the working method is a **git bundle**, applied in
**Command Prompt**:

```
cd /d C:\dev\nacc-sys-v3
git fetch "%USERPROFILE%\Downloads\<bundle-file>" cloud-setup
git merge FETCH_HEAD
git log --oneline -1
git push origin cloud-setup
```

Facts that cost real time when forgotten:

- **The repo lives at `C:\dev\nacc-sys-v3`.** Not under the user profile. The
  Windows account is `User`; an older machine used `talas` and paths from that
  era do not exist any more.
- **Ask what the downloaded file is actually called before writing the fetch
  command.** The browser renames things — `nacc-v3-update.bundle` arrived as
  `naccv3update.bundle`, and a fetch pointed at the wrong name fails with
  *"does not appear to be a git repository"*, which reads like a broken bundle
  rather than a typo.
- Build the bundle from a commit the owner definitely has:
  `git bundle create <file> <their-HEAD>..cloud-setup`.
- Working branch is `cloud-setup`. Verify a push landed with the GitHub MCP
  read tools (`list_branches`) rather than asking.

## Infrastructure (live — reference only, see Scope)

- **Frontend + API**: Render (`nacc-v3-web`, `nacc-v3-api`), Singapore region,
  auto-deploys on push to `cloud-setup`.
- **Database**: Neon serverless PostgreSQL, `ap-southeast-1`. Deliberately not
  in `render.yaml` — Render's free database is deleted after 30 days. Neon's
  browser SQL Editor is the quickest way to run a query; it needs no
  connection string and no local `psql` (which is not on PATH on this machine).
- **Object storage**: Cloudflare R2, bucket `nacc-v3-media`. The API token is
  scoped to that one bucket with Object Read & Write. R2 needs path-style
  addressing and `AWS_REQUEST_CHECKSUM_CALCULATION=when_required`; both are
  already handled in `backend/config/storages.py` and `settings.py`.
- **Google Sign-In**: staff and psychologists only — never administrators. The
  OAuth app must stay **In production**; in Testing mode Google refuses every
  account that is not on the test-user list, which looks exactly like a broken
  button.

## Addresses

PSGC lives in the `locations` app, seeded from a committed JSON file — there is
no live address API and adding one would put a processor in §6 for nothing.
`seed_psgc` and `backfill_psgc --apply` both run from `backend/entrypoint.sh`
on every deploy — Render's Shell tab is paid-only, so nothing here may depend
on running a command by hand. Both are idempotent, and the backfill skips
records that already carry codes so it can never undo an address someone picked
in the form.

## Health check

`https://nacc-v3-api.onrender.com/healthz/` returns
`{"status": "ok", "database": "ok"}`. It proves the database credential and
nothing else — a wrong `DJANGO_SECRET_KEY` still boots the app fine and only
shows up as broken sign-in.

## Local copy

`setup-local.bat` then `run-local.bat` from the repo root — SQLite, files on
disk, no Google sign-in, no email. Verified from an empty database: migrate,
seed_initial_data, seed_psgc, sign in, every screen renders. Details in
docs/LOCAL-SETUP.md.

```
API       http://localhost:8000      Frontend  http://localhost:5173
Health    http://localhost:8000/healthz/
Sign in   admin@racco1.gov.ph / admin1234
```

`run-local.bat` opens two windows and does not reload on backend dependency
changes — restart the API window after touching requirements or settings.

## Demo data

`manage.py seed_demo_data` invents 40 children with six months of history —
remarks, self-reports, appointments — so cross-caseload features have something
to work on. Three cohorts: steady, declining, and one whose self-reports drift
toward distress while the case notes stay reassuring. That last group is the
point; it is what a divergence detector would be built to find.

Refuses to run against a hosted database or with DEBUG=False, and the guard
runs before anything opens a connection.

## The assistant app

Restored 26 Aug 2026 — pre-session briefs, document summaries, remark polish, a
census narrative, usage metrics. On by default; one administrator switch in
Settings, no per-feature flags.

- **Never rename `assistant` to `ai`.** A previous `ai` app was deleted but its
  rows are still in `django_migrations`. Create an app called `ai` again and
  Django sees `ai.0001_initial` already applied, skips it, reports success, and
  the tables are simply never created.
- **Prompts are assembled static-prefix-first.** A fixed instruction block, a
  module constant identical on every call, then the dynamic facts — never the
  other order. That keeps Ollama's prefix cache warm: ~0.37s cached versus
  17-20s cold. A stable prefix is worth roughly 17 seconds a call.
- **No per-request model options.** `generate()` sends `model`, `prompt`,
  `stream` and `system` only. Each distinct option set makes Ollama evict and
  reload the model; an explicit `num_ctx` measured 6x slower end to end.
- **`qwen3.5:2b` does not load on this machine** — it fails allocating a ~2 GB
  buffer. `qwen2.5:3b-instruct` is what everything was built and measured
  against, and it is the default in `AssistantSetting`.
- **Set `OLLAMA_HOST=127.0.0.1`.** It binds `0.0.0.0` by default, which puts an
  unauthenticated model server on the local network. Also
  `OLLAMA_KEEP_ALIVE=-1` (avoids a ~12-16s cold load, costs 1.9 GB resident) and
  `OLLAMA_NUM_PARALLEL=1`.
- **The notes are Taglish, and that breaks things.** Measured: remark polish
  drifts into Tagalog on 67% of Taglish inputs and 0% of English ones, so a
  drifted draft is now rejected rather than shown. Briefs are far better —
  0/60 invented names, 3% drift, median 11.6s. One brief in the wild did invent
  a child's name, so this is not theoretical.
- **`manage.py ai_eval` measures all of that**; `manage.py ai_check` says
  whether the runtime is reachable. Neither runs in the test suite — both need
  a live Ollama. Never claim the output is fine without running `ai_eval`.

## Before committing or bundling anything

Both of these, every time:

```
cd backend && .venv/Scripts/python.exe manage.py test   # 517 tests, ~15 min
cd frontend && npm run lint && npm run build
```

**`npm run build` is not enough on its own.** Vite only reports syntax errors —
a reference to a deleted variable, or a hook left below an early return, builds
perfectly and then throws at runtime. Both have already happened here: removing
the AI layer left a `setPolishJob` call behind, and an inserted `useState`
landed under `if (!data) return …`, which crashed the child report for every
user until someone opened that page.

`npm run lint` catches both. It is already configured with
`plugin:react-hooks/recommended`, so `rules-of-hooks` is on and reports
*"Did you accidentally call a React Hook after an early return?"* by name.

After a change that spans several screens, load each one — a page that renders
nothing still exits `npm run build` with code 0.
