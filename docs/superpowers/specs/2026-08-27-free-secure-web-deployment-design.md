# Free, secure web deployment

**Status:** design, approved in conversation 27 Aug 2026. Not built.
Revised the same day after a spike replaced the model-hosting approach.

## What this is for

A publicly reachable deployment of NACC SYS V3, including the chatbot, at **no
cost**, without exposing a model server and without touching the live Render
deployment.

It exists to be shown — to the agency, to a panel, to anyone with the link.
Visitors sign in with credentials handed out deliberately; the app's own login
is the only gate.

## The two repositories

The fact most likely to cause an expensive mistake, so it comes first.

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
costs nothing (copy-on-write; the free tier allows 10 branches per project),
and is isolated: writes on the branch never reach `main`, so the live Render
app is unaffected and the migrations in this repo that the live deployment does
not have — `clinical.0010_selfreportflag`, `assistant.0003`/`0004` — never
touch production.

The sequence on the branch:

1. **Clear child data** — children and everything hanging off them: clinical
   records, appointments, opinionnaires, self-report flags, assistant jobs.
   Done whether or not real records exist there, so the public demo cannot show
   one by accident.
2. **Import the local demo children**, excluding users.
3. **Reassign** those children to the branch's real psychologist accounts.
4. **Set a known password for one demo account, on the branch only.**

**`seed_demo_data` is never run against a hosted database and its guards are
not weakened.** Its own comment gives the reason: *"Running it against the
agency's real one would mix fictional records into real case files — not a data
loss, something worse: a file that cannot be trusted."* The transfer happens by
`dumpdata` locally and `loaddata` into the branch.

The seeder's four users (`m.bulan@racco1.gov.ph` and the rest) are **dropped
rather than imported**. Email is unique; importing them would collide with real
accounts, and using the real ones is the entire point.

### Files

**A fresh, empty R2 bucket.** No object from the live bucket is copied. The
demo has no reports, consent scans, referrals or child photographs — because it
has none at all, not because they were filtered. A missing file renders as
"no file"; a leaked one is a disclosure.

### Knowingly accepted

**Real staff names and emails are on the branch.** That is the point — the
accounts are why the branch exists. Anyone given administrator credentials can
see the user list. Accepted deliberately, not overlooked.

## Phase 1 — the application

New Render Blueprint from `local-ver`, creating **new services**. The existing
`nacc-v3-api` and `nacc-v3-web` are untouched.

**The service names in `render.yaml` collide with the live ones** and must be
renamed in this repo before any Blueprint is created:

| Live (from `origin`) | Demo (from `local-ver`) |
|---|---|
| `nacc-v3-api` | `nacc-v3-demo-api` |
| `nacc-v3-web` | `nacc-v3-demo-web` |

Two settings differ from the live blueprint:

- `DATABASE_URL` → the **branch** connection string, never `main`.
- The four R2 variables → the **new demo bucket**.

**There is no `ASSISTANT_ENABLED` environment variable**, and `enabled`
defaults to **`True`** on `AssistantSetting`. The assistant is therefore *on* in
a fresh deployment and must be switched off through the administrator control
in Settings as a step after the first deploy. Left on with no model configured,
every call returns 503 — which every screen already absorbs, so nothing breaks;
it is simply untidy.

**Known rough edge:** the chat pill is mounted on every protected screen
regardless of the switch, so it stays visible and answers "The assistant is
unavailable right now." Acceptable for a demo, and deliberately not fixed here.

Render's free plan is 512 MB, 0.1 CPU, sleeps after 15 minutes idle, and allows
750 instance-hours per workspace per month. Two demos that both sleep stay well
inside that. The first visitor after a quiet period waits about a minute.

**Phase 1 is a complete, working demo on its own.** Records, scheduling,
reports, monitoring, self-report flags and care-gap alerts all work with no
model anywhere.

## Phase 2 — the model, hosted

**Cloudflare Workers AI**, called directly from Django over its
OpenAI-compatible REST endpoint. No virtual machine, no tunnel, no firewall, no
server to patch.

An earlier revision of this spec placed Ollama on an Oracle Always Free ARM
instance behind a Cloudflare tunnel. A spike replaced it: Workers AI is faster,
needs no infrastructure, and avoids Oracle's capacity lottery entirely.

### What the spike measured

Against the real `tools.ollama_payload()` schema and the real evaluation cases,
in English and Tagalog:

| Model | Routing | Median |
|---|---|---|
| `@cf/meta/llama-4-scout-17b-16e-instruct` | **33/33** over three passes | **0.6 s** |
| `@cf/openai/gpt-oss-20b` | 11/11 | 0.8 s |
| local `qwen2.5:3b-instruct` (for comparison) | 55/55 | 2.4 s |

Four times faster than the local model, with no measured loss of accuracy.

### The model choice is not cosmetic

`@cf/qwen/qwen3-30b-a3b-fp8` **accepts the tools array and then returns the
call as raw text** in `<tool_call>` tags rather than in the structured
`tool_calls` field. It looks like it works and silently does not.

The chosen model must return structured `tool_calls`. **Llama 4 Scout does.**
Any model change requires re-running the spike, not a hunch.

### Endpoint

```
POST https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/ai/v1/chat/completions
Authorization: Bearer {CF_API_TOKEN}
```

Free allowance is **10,000 neurons per day**, roughly 1,300 responses, shared
across models and reset at 00:00 UTC. The Workers **free plan hard-limits
rather than billing**, so exhaustion is an outage, never a charge.

## Code changes

Four, all small, all independently testable.

### 1. An OpenAI-compatible client

`OllamaClient` speaks Ollama's `/api/chat` and `/api/generate`. A sibling
`OpenAICompatibleClient` speaks `/v1/chat/completions` with a bearer token, and
`get_ai_client()` chooses between them on configuration.

The same client also works against local Ollama's own `/v1` endpoint, so this
is not single-vendor plumbing.

### 2. A hard guard against hosted providers reaching real data

This is the most important change in the document.

The codebase says, deliberately: *"There is deliberately only one provider. A
hosted API would mean sending clinical free text to an outside processor."*
That rule is why the V2 AI layer was removed. Adding a hosted client creates
the capability to break it.

The guard:

- The hosted provider is configured **only** by environment variable, never by
  the administrator-editable `AssistantSetting.ollama_url`. Environment takes
  precedence when set.
- It **refuses to start** unless `ASSISTANT_ALLOW_HOSTED_MODEL=true` is set
  explicitly. Configuring a token is not consent.
- It **logs loudly at boot** when active, naming the provider and model, so
  "which model answered this" is never a guess.
- The live blueprint (`origin`) carries none of these variables, so the live
  system cannot acquire a hosted provider by drift.

### 3. Rate limiting on the assistant endpoints

**There is none anywhere in the application today** — no DRF throttling is
configured and `/api/assistant/ask/` has no throttle class.

This now has a concrete cost: the daily allowance is 10,000 neurons, and one
account can exhaust it. Scoped DRF throttles on the chat, brief, polish and
summary endpoints, with a per-account daily ceiling well under the allowance.

### 4. A model reachability check

`/healthz/` proves the database credential and nothing else. A separate
administrator-only endpoint reports whether the configured model answers, so
"the chatbot is broken" is diagnosable without reading Render logs.

## What the spike did NOT measure

**Only tool routing was tested.** The drafting features — pre-session briefs,
remark polish, document summaries — and the self-report model detector are
prose generation, not tool calling. Their measured behaviour belongs to
`qwen2.5:3b-instruct`:

- remark polish drifts into Tagalog on **67%** of Taglish inputs
- the self-report detector **missed 28%**, including an Ilocano disclosure 3
  times out of 3

**None of those numbers transfer to a different model.** Phase 2 enables the
chatbot only. Any drafting feature on Workers AI requires its own `ai_eval` run
first, and this spec makes no claim about them.

## Risks

**Cloudflare deprecates models.** `@cf/meta/llama-3.1-8b-instruct` was retired
on 2026-05-30 and returns HTTP 410 — the spike hit exactly that. A pinned model
can vanish and take the chatbot with it. Local Ollama never does this. The
configuration therefore names a fallback model, and the reachability check in
change 4 is what surfaces the failure.

**The daily cap is an outage, not a bill.** Exhausting 10,000 neurons stops the
chatbot until 00:00 UTC. Rate limiting is what keeps a demo visitor from
spending the day's allowance in a minute.

**Every question reaches Cloudflare.** Acceptable for fictional children and
unacceptable for real ones — which is the entire reason for the guard.

**Render cold starts.** ~60 seconds after 15 minutes idle. Open the page a
minute before demonstrating to a panel.

**The wrong `DATABASE_URL`** points the public demo at production. Set once, in
the dashboard, and worth checking twice.

**A bare `git push` deploys the demo** once the Blueprint is connected.

## Non-goals

- **No real children's data.** The demo's children are fictional. No
  anonymisation is built, because with no real records present there is nothing
  to anonymise — and an anonymiser whose failure mode is a child's disclosure is
  not worth building to solve a problem that can simply be absent.
- **No files.** The demo bucket starts and stays empty.
- **No drafting features on the hosted model** until measured separately.
- **Nothing is pushed to `origin`**, and the live Render deployment is not
  modified, redeployed, or reconfigured.
- **No paid tier**, on any service.

## What is not claimed

- That free tiers persist. Render shortened its idle timeout this year and
  Cloudflare retires models on its own schedule.
- That routing quality holds on any model other than the one measured.
- That this is suitable for real case data. It is not, and nothing in it was
  designed for that.
