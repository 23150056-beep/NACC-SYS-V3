# Working on NACC SYS V3

Notes for whoever (or whatever) picks this up. Read this before offering to push
anything — the last session burned an hour rediscovering the first two sections.

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

**The agent cannot push.** From the sandbox, `git push` returns 403 at the
proxy, and the GitHub MCP tools return `403 Resource not accessible by
integration` even on a bare branch creation. Do not spend time re-testing this.
Every push goes through the owner, by hand, on their machine.

The working method is a **git bundle**, applied in **Command Prompt**:

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

## Deployment shape

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

## Health check

`https://nacc-v3-api.onrender.com/healthz/` returns
`{"status": "ok", "database": "ok"}`. It proves the database credential and
nothing else — a wrong `DJANGO_SECRET_KEY` still boots the app fine and only
shows up as broken sign-in.

## Before bundling anything

Both of these, every time:

```
cd backend && .venv/bin/python manage.py test     # 362 tests
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
