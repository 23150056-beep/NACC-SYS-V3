# Running NACC SYS V3 on your own machine

A local copy that behaves like the live system but touches none of it. Useful
for trying changes, working offline, and demonstrating without depending on a
free-tier service being awake.

## What is different from the cloud

| | Cloud | Local |
|---|---|---|
| Database | Neon (PostgreSQL) | SQLite, a file in `backend/` |
| Uploaded files | Cloudflare R2 | `backend/media/` on disk |
| Google Sign-In | on | off — the button hides itself |
| Assignment emails | Brevo | not sent; skipped with a log line |
| Addresses (PSGC) | seeded on deploy | seeded by the setup script |

Nothing local can reach the live database or the live bucket. Records you make
here exist only here.

## First time

Double-click **`setup-local.bat`** in the repository root.

It checks that Python and Node are installed, then creates the environment,
installs packages, builds the database, and loads the roles, the default
administrator and the 3,265 Region I barangays. Ten minutes or so, mostly
downloads.

If it stops, the message says which step failed. Re-running is safe — it reuses
what already worked.

### Prerequisites

- **Python 3.11+** — <https://www.python.org/downloads/>
  Tick **"Add python.exe to PATH"** during install. This is the step people
  miss, and everything afterwards fails with *"python is not recognized"*.
- **Node.js LTS** — <https://nodejs.org/>

## Every time after that

Double-click **`run-local.bat`**.

Two windows open (API and frontend) and your browser opens on
<http://localhost:5173>. Close the windows to stop.

Sign in as `admin@racco1.gov.ph` / `admin1234`.

## Filling it with something to look at

A fresh database has no children, which makes every cross-caseload screen look
broken rather than empty:

```
cd backend
.venv\Scripts\python manage.py seed_demo_data
```

Invents 40 children across the four Region I provinces, with roughly six months
of remarks, self-reports, appointments and problems behind them. Everyone in it
is fictional — names, notes and answers were all written for that file.

It refuses to run against a hosted database or with `DJANGO_DEBUG=False`, so it
cannot reach the live system. `--purge` starts clean, `--seed N` changes the
caseload, and the same seed always produces the same people — so a demo can be
reproduced exactly.

The notes deliberately mix English, Tagalog and Ilocano, because notes written
in Region I do.

## Starting over

Delete `backend/db.sqlite3` and run `setup-local.bat` again for an empty
database with just the roles, the administrator and the addresses.

## Running the tests

```
cd backend
.venv\Scripts\python manage.py test
```

379 tests. This is the local copy's real purpose: change something, prove it
still works, and only then send it to the live system.

## Manual setup, if you prefer

```
cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
copy .env.example .env
.venv\Scripts\python manage.py migrate
.venv\Scripts\python manage.py seed_initial_data
.venv\Scripts\python manage.py seed_psgc
.venv\Scripts\python manage.py runserver

cd ..\frontend
copy .env.example .env
npm install
npm run dev
```
