# NACC SYS V2 — Office PC Deployment & Backup Guide

Target: a single office PC/server at RACCO I (Windows, 8–16 GB RAM).
Stack: Django 5.1 + PostgreSQL + React (built static) + optional Ollama.

## 1. One-time setup

### Prerequisites
- Python 3.12+ · Node 20+ (build only) · PostgreSQL 16+ · (optional) Ollama

### Database
```powershell
# in psql as the postgres superuser:
CREATE DATABASE nacc_v2;
```

### Backend
```powershell
cd backend
python -m venv venv
.\venv\Scripts\pip install -r requirements.txt
Copy-Item .env.example .env
# edit .env:
#   DJANGO_SECRET_KEY  -> long random string
#   DJANGO_DEBUG=False
#   DB_ENGINE=postgres, DB_PASSWORD=<the password chosen at PostgreSQL install>
.\venv\Scripts\python.exe manage.py migrate
.\venv\Scripts\python.exe manage.py seed_initial_data   # roles + default admin
```

Default admin: `admin@racco1.gov.ph` / `admin1234` — **change this password
immediately** via User Management.

### Frontend
```powershell
cd frontend
npm install
npm run build        # outputs dist/ — serve with any static server
```
For LAN use, the simplest run mode is `npm run dev` (port 5173) next to
`manage.py runserver` (port 8000); set `VITE_API_BASE_URL` in `frontend/.env`
to `http://<server-ip>:8000/api` for other machines on the network.

### Optional: local AI (Ollama)
```powershell
winget install ollama.ollama
ollama pull qwen2.5:7b-instruct     # ~5 GB; needs ~8 GB free RAM
```
Then in the app: Settings → Local AI Layer → enable the master switch.
If the machine has only 8 GB RAM, keep AI off during heavy use — every
feature works without it (care-gap alerts are deterministic and always on).

## 2. Backup (do this weekly, before any update)

Two things hold all data: the PostgreSQL database and the media folder.

```powershell
# database
pg_dump -U postgres -d nacc_v2 -F c -f "D:\backups\nacc_v2_$(Get-Date -Format yyyyMMdd).dump"
# uploaded files (reports, consent scans, photos)
Copy-Item backend\media "D:\backups\media_$(Get-Date -Format yyyyMMdd)" -Recurse
```
Keep at least 4 rotations on an external drive stored separately (child data —
RA 10173 duty of care).

## 3. Restore

```powershell
psql -U postgres -c "DROP DATABASE IF EXISTS nacc_v2; CREATE DATABASE nacc_v2;"
pg_restore -U postgres -d nacc_v2 "D:\backups\nacc_v2_YYYYMMDD.dump"
Copy-Item "D:\backups\media_YYYYMMDD\*" backend\media -Recurse -Force
```

## 4. Security checklist (per release)

- `DJANGO_DEBUG=False`, unique `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`
  restricted to the server name/IP.
- Uploaded files are served **only** through authenticated endpoints
  (`/api/report-files/<id>/download/`, `/api/consents/<id>/download/`);
  the media folder must never be exposed by a web server directly.
- No instrument content in the database — spot-check `tbl_instrument_catalog`
  (titles/metadata only) and `tbl_agency_form_template` (attestation set).
- Access matrix (enforced server-side, verify after permission changes):

| Capability | Admin | Psychologist | Staff |
|---|---|---|---|
| Users / roles | full | — | — |
| Child & guardian records | full | read (assigned only) | create/edit |
| Terminate case (reason required) | yes | own cases | — |
| Instrument catalog / agency forms | all | own | — |
| Pre-assessment flow, remarks, plans, results, report uploads | yes | own children | read-only |
| Consent / interview / problem records | write | own children | read-only |
| Availability | all | own | read |
| Book appointments | yes | own calendar | inside availability |
| Appointment status | yes | own | cancel only |
| Agency summary / census | yes | — (dashboard is scoped) | yes |
| AI feature flags | yes | — | — |
| AI drafts (brief/summary/polish) | yes | own children | narrative only |
