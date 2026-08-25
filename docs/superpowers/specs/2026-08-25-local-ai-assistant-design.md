# Local AI Assistant — Design

**Date:** 2026-08-25
**Status:** Draft for review
**Scope of this spec:** the assistant **spine** plus **slice 1 (drafting features)**.
Later slices are named at the end and get their own specs.

## Context

V2 shipped an AI layer on a local Ollama model. V3 removed it on 2026-08-18
(`69a8934`, and `activity/0003_drop_ai_tables.py`) because Render has no GPU and
a hosted provider would have meant sending clinical free text to a processor
outside the agency's data-processing agreements.

Two things have changed:

1. **Deployment is local for now.** Render is parked. Everything — Django, the
   database, Ollama — runs on one machine. The transport problem that killed the
   V2 layer does not exist in this configuration.
2. **The privacy argument has moved.** "Case text never leaves the building" was
   already void in V3: records live in Neon (`ap-southeast-1`) and R2. The live
   question is narrower — *does a third-party AI processor see clinical free
   text?* A self-hosted model answers that cleanly, whichever machine it runs on.

This spec therefore assumes **on-premises Ollama only**. No hosted provider is
built. The client seam is kept so adding one later is an addition, not a rewrite,
but choosing to add one is a separate decision with its own privacy review.

## Measured constraints

Everything below was measured on the target machine on 2026-08-25, not estimated.
These numbers are the reason for several design decisions, so they are recorded
here rather than in a commit message.

**Hardware:** 7.80 GB RAM total, **1.16 GB free** under normal dev load;
i5-1135G7 (4 cores / 8 threads); Intel Iris Xe integrated graphics — **no CUDA,
so Ollama runs on CPU**.

**Models:**

| Model | Result |
|---|---|
| `qwen3.5:2b` (Q8_0, vision, thinking, 256K ctx) | **Does not load.** `failed to allocate buffer of size 2065712384`. Vision projector + Q8 exceeds free RAM. |
| `qwen2.5:3b-instruct` (Q4_K_M, tools, 32K ctx) | **Loads.** 11.4 s cold, then 6–10 tok/s. |

`qwen2.5:3b-instruct` is the model this spec builds on. Vision — and therefore
any scanned-form reading — is **out of scope on this hardware**.

**Latency:** warm tool call 4.1–8.7 s (typically ~5 s). Prose generation 9.8 s
for 45 tokens. A ~400-token brief is therefore ~40 s.

**Tool-calling accuracy**, identical 11-case set, 2 reps each:

| Configuration | Right tool | Right tool + args |
|---|---|---|
| Naive schemas | 77% | 64% |
| Hardened schemas + escape hatch | 100% | 82% |
| The above + few-shot examples | **100%** | **91%** |

**Prefix caching is worth ~17 s per call.** A ~1000-token static prefix (system
prompt + tool definitions) prefills in **0.37 s cached** versus **17–20 s cold**.
Separately, **changing any model option forces a reload** (~5–6 s) — an explicit
`num_ctx` made calls 6× slower than leaving it unset.

Two model behaviours that server-side code must handle:

- **Enums are not enforced.** Asked in Filipino, the model returned
  `{"when": "bukas"}` where the enum allowed only
  `today|tomorrow|this_week|next_week`. Four attempts, four failures.
- **Argument keys can be malformed.** Observed `{"when: ": "today"}` — key
  `"when: "`, not `"when"`. A naive `args["when"]` raises `KeyError`.

## Invariants

Carried forward from the V2 layer, and unchanged:

- Every feature sits behind its own flag; the system is fully functional with AI
  off, degrading with 503 rather than breaking.
- Every output is a **draft a human confirms**. Nothing is auto-applied.
- Every call is audited.
- Prompts carry the minimum necessary data (RA 10173).
- No copyrighted instrument content in any prompt.
- **No scores, ratings, or classifications of children.** Deterministic code does
  arithmetic; the model only writes prose.

Two invariants added by the measurements above:

- **Tool arguments are untrusted input.** Validate keys and values in Python
  against the schema before they reach a queryset — the model does not honour
  the schema.
- **Permissions never come from the model.** Scope is derived from
  `request.user`, exactly as in `_ChildScopedClinicalViewSet`. No tool takes an
  `assigned_to_me`-style parameter, so the model cannot get it wrong.

## Architecture — the spine

### App name

The new app is **`assistant`**, not `ai`.

`activity/0003_drop_ai_tables.py` dropped `tbl_ai_job` and `tbl_ai_setting` but
deliberately left the `ai` rows in `django_migrations`. Any database that lived
through that removal would see a recreated `ai.0001_initial` as already applied
and silently skip creating the tables, failing at runtime with "no such table".
The local SQLite database is currently clean (verified: 0 rows), but a fresh app
label makes the question moot everywhere. Tables: `tbl_assistant_setting`,
`tbl_assistant_job`.

### Models

`AssistantSetting` — singleton (pk=1), mirroring V2's `AISetting` minus the
hosted provider:

```
enabled                   bool, default False   # master switch
feature_brief             bool, default True
feature_doc_intelligence  bool, default True
feature_remark_polish     bool, default True
feature_census_narrative  bool, default True
ollama_url                url,  default http://localhost:11434
model_name                str,  default qwen2.5:3b-instruct
updated_at                datetime
```

`AssistantJob` — one audit row per call: `job_type`, `input_ref`
(`"child:12"`), `output_text`, `model_used`, `latency_ms`, `ok`, `error`,
`outcome` (`pending|accepted|edited|discarded`), `created_by`, `created_at`.

The V2 design's separate legacy `accepted` boolean is **not** carried over —
nothing in V3 reads it, so `outcome` stands alone.

### `assistant/services.py`

- `AIUnavailable(Exception)`
- `NullClient` — `available = False`; `generate()` raises `AIUnavailable`.
- `OllamaClient(base_url, model)` — POSTs `/api/generate`, returns stripped text,
  raises `AIUnavailable` on any transport or decode failure. Lifted from V2's
  proven implementation.
- `get_ai_client()` — returns `OllamaClient` when the master switch is on, else
  `NullClient`.
- `run_job(job_type, prompt, *, system, input_ref, user)` — the single entry
  point. Acquires the generation lock, calls the client, normalizes the output,
  writes the `AssistantJob` row (success **and** failure), returns
  `(text, job)`.
- `_normalize_output(text)` — deterministic punctuation cleanup: curly quotes to
  ASCII, en/em dash to hyphen, non-breaking space to space. Post-processing is
  reliable where prompting about punctuation is not.

**`_GENERATION_LOCK`** — a module-level `threading.Lock`. On 4 CPU cores,
concurrent generations make every request slower rather than parallel, and each
parallel slot multiplies the KV cache against 1.16 GB of free RAM. One
generation at a time, always.

**No per-request model options.** `run_job` sends `model`, `prompt`, `system`,
`stream: false` and nothing else. No `num_ctx`, no `temperature` override — each
distinct option set evicts and reloads the model.

### Prompt construction rule

Every prompt is assembled **static-prefix-first**:

```
[ static system prompt ] [ static instructions ] [ dynamic case data ]
```

Anything varying per call — today's date, the child's name, the user's name —
goes **after** the static block. Putting the date at the top costs ~17 s of
re-prefill on every single call. `assistant/prompts.py` holds the static halves
as module constants so they are literally the same bytes each time.

### Environment and operations

Deployment notes, not code — but the design depends on them:

```
OLLAMA_KEEP_ALIVE=-1        # avoid the 11.4 s cold load; costs 1.9 GB resident
OLLAMA_NUM_PARALLEL=1       # parallel slots multiply the KV cache
OLLAMA_MAX_LOADED_MODELS=1  # never hold two models against 7.8 GB
```

`manage.py ai_check` — a smoke command that reports whether Ollama is reachable,
whether the configured model is present, and a measured round-trip latency. It
exists because "sign-in works but drafts silently 503" is otherwise hard to
diagnose, and this project cannot rely on a shell being available.

## Slice 1 — drafting features

Four features, all sharing one pattern: build prompt → `run_job` → return draft →
human edits → human confirms → outcome recorded. They are sequenced so the
cheapest one proves the spine.

**S1.1 — Remark polish** (`feature_remark_polish`). Measured at 9.8 s and
verified to produce clean, faithful output. `POST /api/assistant/polish-remark/`
takes raw text, returns a polished draft. The psychologist edits and saves; the
saved text is compared to the draft to set `outcome` (`accepted` if identical
after whitespace normalization, else `edited`). Built first because it touches
one field on one screen and proves the whole spine end to end.

**S1.2 — Pre-session brief** (`feature_brief`). At ~40 s a brief is unacceptable
on a button press, so the normal path is **pre-generated** and the on-demand
generator becomes a fallback. Three endpoints, using V2's approved design:

- `POST /api/assistant/brief/child/<id>/` — generates one now. Used only as the
  fallback when no prefetched brief exists, and behind an explicit
  **Regenerate** action. This is the ~40 s path, and the UI says so.
- `GET /api/assistant/brief/child/<id>/latest/` — newest `ok` brief job for that
  child created **today**; 404 when none. Tried **first** by every caller, so the
  common case is instant and stamped with the time it was drafted.
- `POST /api/assistant/prefetch-briefs/` — for the caller's today/scheduled
  appointments, generates missing briefs **sequentially in one daemon thread**,
  returns `{queued, skipped}` immediately. A module-level in-flight set plus lock
  prevents duplicate generation across requests; the thread closes its DB
  connection when finished.
- `Schedule.jsx` fires the prefetch fire-and-forget after appointments load;
  errors are ignored, because degradation must be silent.

Prompt hardening carried from the V2 design and never shipped: the brief prompt
includes `age` (computed from `Child.birth_date`, literal `unknown` when null)
and `gender` (or `unspecified`), plus *"Use only the facts provided above. Do not
state age, gender, or any other detail not given. Refer to the child by first
name only."* These fix three defects observed live in V2 — the model guessed the
child's age, drifted between pronouns, and emitted curly quotes.

**S1.3 — Document summarization** (`feature_doc_intelligence`). Both
`PsychologicalReport` and `CaseReferral` already carry `extracted_text`,
`ai_summary`, and `ai_summary_confirmed` — the removal kept those columns, so
**no model migration is needed**. Endpoints mirror the V2 shape:
`POST /api/assistant/summarize-report/<id>/`,
`POST /api/assistant/confirm-summary/<id>/`, and the `case-referral` pair.
Permission: admin/staff, or the child's assigned psychologist. Confirming sets
the confirmed text and flag and records `outcome` by comparing confirmed text to
`job.output_text`.

**S1.4 — Census narrative** (`feature_census_narrative`). A prose summary of the
agency figures already computed by `clinical/reports.py:summary()` and rendered
on `AgencySummary.jsx`. **The deterministic code supplies every number; the model
only writes sentences around them** — the prompt receives finished figures and is
instructed to restate, never to calculate. Admin and staff only.

**Settings panel.** `Settings.jsx` (admin only) regains the AI section: master
switch, per-feature flags, Ollama URL, model name, an `ai_check` result readout,
and a usage table per feature — runs, success rate, average latency, and the
accepted/edited/discarded breakdown from `AssistantJob.outcome`. That table is
the evaluation evidence for the capstone as much as it is an operational view.

**Not in slice 1:** streaming. Briefs are prefetched and everything else is
around 10 s, so a spinner is honest and sufficient. Streaming arrives with the
chatbot, which needs it.

## Error handling

A single `_gate(feature_flag)` helper, reused by every endpoint: master switch
off, feature flag off, or `AIUnavailable` all produce **503 with a plain
message**. Callers already handle a missing draft, so the UI degrades to
"unavailable" rather than breaking.

Endpoints that only read history — `latest`, the metrics table — work with AI
switched off, because they touch no model.

Failed calls still write an `AssistantJob` row with `ok=False` and the error, so
"it never works after 4 p.m." is answerable from data.

## Testing

Extend the existing suite (`cd backend && .venv/bin/python manage.py test`,
currently 379 tests) using V2's mocked-client pattern — no test may require a
running Ollama.

- `_normalize_output` against mixed Unicode punctuation.
- Prompt assembly: brief contains age and gender; the unknown-birthdate path;
  **static prefix is byte-identical across two calls with different children**
  (this is the prefix-caching guarantee, and it is easy to break accidentally).
- `_gate` degradation: master off, feature off, client raising `AIUnavailable`.
- The permission matrix for every endpoint, including a psychologist reaching for
  another psychologist's child.
- `latest` scoping: today-only, `ok`-only.
- Prefetch: dedup via the in-flight set, role scoping, thread patched to run
  synchronously.
- Confirm sets `outcome` correctly — `accepted` when identical, `edited` when not.
- An `AssistantJob` row is written on failure, not only on success.

Frontend, per CLAUDE.md: `npm run lint` **and** `npm run build`, then open each
touched screen — a page that renders nothing still exits `build` with code 0.

## Follow-on specs

Named here so the decomposition is on record; each gets its own spec.

1. **Semantic search.** `nomic-embed-text` (274 MB) plus pgvector. Powers
   "find children with similar presenting concerns" and gives the chatbot real
   retrieval.
2. **The chatbot.** Tool-calling assistant docked in `Shell` (`App.jsx:26`), so
   it is available on every protected route. Design inputs are already validated
   — see the appendix.
3. **Divergence detector.** Deterministic trend comparison between
   `OpinionnaireInvite.answers` and the `RemarkNote` timeline, with the model
   writing **only** the explanation. `seed_demo_data`'s `divergent` cohort exists
   precisely to develop this against. A triage signal, never a score on a child.
4. **Quality gates.** Report completeness check before sign-off; prose framing on
   top of the deterministic `care_gaps.py` alerts.

## Appendix — validated chatbot design inputs

Recorded now so the spike is not repeated. All measured, not assumed.

- **Tool schema rules:** no optional free-text parameters, ever. Enum-constrained
  and required parameters survived every call; optional free-text parameters were
  dropped on every call. Push variation into more tools with tighter schemas
  rather than more parameters per tool.
- **Include an `answer_directly(reason)` escape hatch.** Small models would
  rather call something than nothing; without it, "Thanks, that's all" invoked a
  care-gap query.
- **Include few-shot examples** in the static prefix — worth 9 points (82% → 91%)
  and free at runtime once the prefix is cached.
- **Write descriptions in the user's vocabulary, with explicit negatives**
  ("…who they are seeing… Do NOT use this to search for children"). This alone
  took tool selection from 77% to 100%.
- **Normalize argument keys and validate enum values server-side**, with a small
  alias table (`bukas → tomorrow`, `ngayon → today`). This is what takes 91% to
  100%, and it is deterministic, instant, and free.
- **Echo the interpretation in the UI** — "Looking up: active children · concern:
  school refusal" — before showing results, so a dropped filter is visible rather
  than a plausible wrong answer.
- **Render tool results as components; do not send them back to the model for
  prose.** This is the largest single win available: it cuts a turn from ~20 s to
  ~5 s *and* removes the only step where real child data passes through the model
  and could be hallucinated. Reserve a second model call for genuine synthesis,
  labelled as a draft.
- **English only at launch**, stated in the UI, until the alias table is proven.

## Non-goals

No hosted or cloud AI provider. No vision or scanned-form reading (the hardware
cannot load the model). No queue infrastructure — a guarded daemon thread is
enough at clinic scale. No scoring or classification of children. No
auto-applying a draft anywhere. No model fine-tuning. No streaming in slice 1.
