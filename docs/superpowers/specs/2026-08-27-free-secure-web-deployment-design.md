# Free, secure web deployment

**Status:** design, approved in conversation 27 Aug 2026. Not built.

## What this is for

A publicly reachable deployment of NACC SYS V3, including the chatbot and the
drafting assistant, at **no cost**, without exposing a model server to the
internet and without touching the live Render deployment.

It exists to be shown — to the agency, to a panel, to anyone with the link.
Visitors sign in with credentials handed out deliberately; the app's own login
is the only gate.

## The two repositories

This is the fact most likely to cause an expensive mistake, so it comes first.

| Remote | Repository | Deploys |
|---|---|---|
| `origin` | `nacc-sys-v3` | the **live** Render services `nacc-v3-api`, `nacc-v3-web` |
| `local-ver` | `NACC-SYS-V3.1-LOCAL-VER` | nothing today; the **demo**, after Phase 1 |

The demo deploys from `local-ver`. **Nothing in this design pushes to
`origin`**, so the live services stay where they are and no live deploy is
triggered at any point.

**After Phase 1, `git push` auto-deploys the demo.** CLAUDE.md currently says
`git push` is "safe", which was true when written and stops being true the
moment the Blueprint is connected. That line is corrected as part of Phase 1 —
otherwise a later session reads it and pushes a half-finished branch to a
public URL.

## Data: accounts from Neon, children from local

The demo runs on a **Neon branch**, never on `main`.

**Why a branch.** The value of the Neon database is the **user accounts already
created there** — real staff and psychologists, with their roles. The children
are the fictional ones from `seed_demo_data`. A branch inherits the accounts,
costs nothing (copy-on-write, and the free tier allows 10 branches per
project), and is isolated: writes on the branch never reach `main`, so the live
Render app is unaffected and the migrations in this repo that the live
deployment does not have — `clinical.0010_selfreportflag`,
`assistant.0003`/`0004` — never touch production.

The sequence on the branch:

1. **Clear child data.** Children and everything hanging off them: clinical
   records, appointments, opinionnaires, self-report flags, assistant jobs.
   Done whether or not real records exist there, so the public demo cannot show
   one by accident.
2. **Import the local demo children**, excluding users.
3. **Reassign** those children to the branch's real psychologist accounts.
4. **Set a known password for one demo account, on the branch only.**

**`seed_demo_data` is never run against a hosted database, and its guards are
not weakened.** Its own comment states the reason: *"Running it against the
agency's real one would mix fictional records into real case files — not a data
loss, something worse: a file that cannot be trusted."* The transfer happens by
`dumpdata` locally and `loaddata` into the branch, so both guards stand
untouched.

The seeder's four users (`m.bulan@racco1.gov.ph` and the rest) are **dropped
rather than imported**. Email is unique; importing them would collide with real
accounts, and the whole point is to use the real ones.

### Files

**A fresh, empty R2 bucket.** No object from the live bucket is copied. The
demo has no reports, consent scans, referrals or child photographs — because it
has none at all, not because they were filtered. A missing file renders as
"no file"; a leaked one is a disclosure.

### What is knowingly accepted

**Real staff names and emails are on the branch.** That is the point — the
accounts are why the branch exists. Anyone given administrator credentials can
see the user list. For a government agency those names are largely already
public, and this was accepted deliberately rather than overlooked.

## Phase 1 — the application

New Render Blueprint from `local-ver`, creating **new services**. The existing
`nacc-v3-api` and `nacc-v3-web` are untouched.

**The service names in `render.yaml` collide with the live ones** and must be
renamed in this repo before any Blueprint is created:

| Live (from `origin`) | Demo (from `local-ver`) |
|---|---|
| `nacc-v3-api` | `nacc-v3-demo-api` |
| `nacc-v3-web` | `nacc-v3-demo-web` |

Everything else in the blueprint carries over. Two settings differ:

- `DATABASE_URL` → the **branch** connection string, never `main`.
- The four R2 variables → the **new demo bucket**.

**There is no `ASSISTANT_ENABLED` environment variable**, and `enabled`
defaults to **`True`** on `AssistantSetting`. So the assistant is *on* in a
fresh deployment and must be switched off deliberately, through the existing
administrator control in Settings, as a step after the first deploy. Left on
with no model reachable, every call returns 503 — which every screen already
absorbs, so nothing breaks; it is simply untidy.

**Known rough edge for Phase 1:** the chat pill is mounted on every protected
screen regardless of the switch, so it stays visible and answers "The assistant
is unavailable right now." Acceptable for a demo, and deliberately not fixed
here — hiding it is a feature change, not a deployment concern, and belongs in
its own piece of work if it matters.

Render's free plan is 512 MB and 0.1 CPU, sleeps after 15 minutes idle, and
allows 750 instance-hours per workspace per month. Two demos that both sleep
stay well inside that. The first visitor after a quiet period waits about a
minute.

**Phase 1 is a complete, working demo on its own.** Every assistant feature
already degrades to a message the screen absorbs, so records, scheduling,
reports, monitoring, self-report flags and the care-gap alerts all work with no
model anywhere. Only drafting and the chatbot are absent. This matters because
Phase 2 may simply not be available when wanted — see Risks.

## Phase 2 — the model, with nothing listening

An Oracle Cloud **Always Free** ARM instance (Ampere A1, Ubuntu). As of
15 June 2026 the tier is **2 OCPU / 12 GB RAM** — halved from 4/24 with no
announcement. 12 GB is still more memory than the development laptop has.

On the instance:

- **Ollama bound to `127.0.0.1`.** Never `0.0.0.0`. It binds to all interfaces
  by default, which is how an unauthenticated model server ends up reachable.
- **`cloudflared`** dials *out* to Cloudflare and holds the connection open.
- **All inbound denied** — both the Oracle security list and `ufw`. No open
  port, nothing to scan, nothing to reach even knowing the address.
- **Cloudflare Access** in front of the tunnel, requiring a **service token**.
  Render authenticates at Cloudflare's edge; unauthenticated requests never
  arrive at the machine.

The property that makes this the chosen approach: **an attacker cannot reach
the box even knowing it exists.** A public endpoint behind a bearer token was
considered and rejected — it is simpler, but it leaves something listening on
infrastructure nobody will patch.

## Code changes

Three, all small, all independently testable.

### 1. The client can authenticate, and the URL comes from the environment

`OllamaClient` sends no credentials today and has nowhere to put any. It gains
optional headers read from **environment variables, not the database**.

`OLLAMA_URL` from the environment **takes precedence over
`AssistantSetting.ollama_url`** when set. This is a security fix, not
convenience: `ollama_url` is an administrator-editable field, so on a public
demo anyone holding administrator credentials could repoint the model server at
a host they control and capture every prompt. Environment wins, and the token
lives only where no form can reach it.

Local development is unaffected — with the variables unset, the database value
is used exactly as now.

### 2. Rate limiting on the assistant endpoints

**There is none anywhere in the application today** — no DRF throttling is
configured and `/api/assistant/ask/` has no throttle class.

Every generation takes a process-wide lock. On a public demo one signed-in
account can hold that lock continuously, making the assistant unusable for
everyone else and pinning the Oracle CPU indefinitely. Scoped DRF throttles on
the chat, brief, polish and summary endpoints.

### 3. A model reachability check

The existing `/healthz/` proves the database credential and nothing else. A
separate administrator-only endpoint reports whether the model host answers, so
"the chatbot is broken" is diagnosable without SSH into Oracle.

## Risks, in the order they are likely to bite

**Oracle ARM capacity.** "Out of Capacity" is common and people retry for days.
Phase 2 may not start when wanted. This is the entire argument for Phase 1
standing alone.

**Oracle halved this tier in June 2026 without announcing it**, and may do so
again. Nothing here should be load-bearing for anything that matters.

**Render cold starts.** ~60 seconds after 15 minutes idle. Open the page a
minute before demonstrating to a panel.

**The wrong `DATABASE_URL`.** Pasting `main` instead of the branch points the
public demo at production. The connection string is set once, in the Render
dashboard, and is worth checking twice.

**A bare `git push` deploys the demo** once the Blueprint is connected.

## Non-goals

- **No real children's data.** The demo's children are fictional. No
  anonymisation of real records is performed, because none are present — an
  anonymiser whose failure mode is a child's disclosure is not worth building
  when the alternative is having no real records at all.
- **No files.** The demo bucket starts and stays empty.
- **Nothing is pushed to `origin`,** and the live Render deployment is not
  modified, redeployed, or reconfigured.
- **No paid tier**, on any of the four services.

## What is not claimed

- That the free tiers will persist. Oracle already cut theirs mid-year, and
  Render shortened its idle timeout.
- That Phase 2 will be available on demand — ARM capacity is genuinely scarce.
- That this is suitable for real case data. It is not, and nothing in it was
  designed for that.
