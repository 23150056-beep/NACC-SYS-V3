# Assistant Chatbot — Design

**Date:** 2026-08-26
**Status:** Draft for review
**Builds on:** `docs/superpowers/specs/2026-08-25-local-ai-assistant-design.md` (the
assistant spine and its four drafting features, now shipped)

## Context

The spine is live: `assistant/services.py` (client seam, generation lock, audited
`run_job`), `assistant/prompts.py`, `AssistantBaseView` (503 degradation),
`_visible_children` role-scoping, feature flags, a usage table, and 100 tests.
Nothing here rebuilds any of that.

This spec adds the **chatbot** — follow-on #2 from the parent spec, whose
appendix already records the validated design inputs so the spike is not
repeated.

**Follow-on #1 (semantic search) is deliberately skipped.** It assumed pgvector;
local development runs on SQLite, where pgvector does not exist. The chatbot as
designed needs no retrieval, so it is built first and the ordering in the parent
spec is superseded.

## Measured constraints

Re-measured 2026-08-26 on the target machine, with Ollama running:

- **7.8 GB total RAM, 2.31 GB free.** `qwen2.5:3b-instruct` needs ~1.9 GB
  resident — it fits, with little headroom.
- **The model is not currently resident between calls.** `OLLAMA_KEEP_ALIVE` is
  unset, so a first call pays ~11–16 s of cold load (observed: 15.9 s for a
  one-word reply).
- **CPU-only**, ~10 tok/s generation, ~50–60 tok/s prefill.
- **Prefix caching is worth ~17 s per call** — a ~1000-token static prefix
  prefills in 0.37 s cached versus 17–20 s cold.

From the parent spec's spike, on the identical case set:

| Configuration | Right tool | Right tool + args |
|---|---|---|
| Naive schemas | 77% | 64% |
| Hardened schemas + escape hatch | **100%** | 82% |
| The above + few-shot | **100%** | **91%** |

The residual 9% is a single failure mode: **the model does not honour its own
enums.** Asked in Tagalog it returned `{"when": "bukas"}` where the enum allowed
only `today|tomorrow|this_week|next_week`. A deterministic alias table closes it.

## Invariants

Inherited from the parent spec, unchanged: off behind a flag; 503 degradation;
every call audited; scope from `request.user`; no scores, ratings or
classifications of children; on-premises only.

Four added by this design:

1. **The model never generates prose.** Its entire output is a tool name and
   arguments. Every word a user reads is either database content rendered by a
   component, or fixed application copy.
2. **Tool results never enter a prompt.** Child names, dates, remark text and
   counts go from the database straight to the UI. The only clinical text
   reaching the model is what the user typed.
3. **Every tool is read-only.** The chatbot cannot create, edit or delete a
   record.
4. **Tool arguments are untrusted input**, validated in Python against the
   schema before reaching a queryset — because the model demonstrably ignores
   the schema.

## Architecture — one turn

```
question ──▶ POST /api/assistant/ask/   {"question": "who needs follow-up?"}
                  │
                  ├─ gate()                         503 when off or unreachable
                  ├─ length check (<=150 chars)     400 otherwise
                  ├─ run_job("chat", ...)           model returns ONLY a tool call
                  ├─ validate(tool, args)           normalize · coerce · alias · reject
                  ├─ resolve(request, tool, args)   real queryset, caller's own scope
                  └─▶ {"tool", "echo", "result", "job_id"}
                            │
                      frontend renders a component
```

There is no second model call. That single decision buys the three things this
design rests on: a turn costs ~5 s rather than ~20 s; clinical data cannot be
hallucinated because it never passes through the model; and the prompt stays a
fixed size so the prefix cache stays warm.

**Stateless by design.** Each question is an independent request — the prompt is
always `static prefix + one question`. History would sit *after* the cached
prefix and be re-prefilled at CPU speed every turn, adding ~5–10 s per exchange
and making cost unpredictable. The UI keeps past answers on screen, so the
conversation looks continuous while the model sees one question at a time.

## The tool registry

`assistant/tools.py` — a new module. Each entry is `{schema, resolve}`; adding a
tool is one entry, and the eval harness iterates the registry.

| Tool | Parameters | Resolves to |
|---|---|---|
| `list_my_appointments` | `when` (enum: `today`/`tomorrow`/`this_week`/`next_week`) | `Appointment` filtered `psychologist=request.user`, `status=SCHEDULED`, in range |
| `count_my_children` | `status` (enum: `active`/`terminated`/`any`) | count over `_visible_children(request)` |
| `search_children_by_concern` | `concern` (**required** string) | `_visible_children` with a matching open problem (see below) |
| `get_child_summary` | `name` (**required** string) | one child (see below) |
| `list_care_gaps` | none | `compute_alerts(_visible_children(request))` |
| `answer_directly` | `reason` (enum) | fixed copy — no query, no model prose |

**One tool set for every role**, not one per role. Scoping happens server-side,
so an administrator asking "who am I seeing today" honestly gets nothing — they
see nobody. One set also means **one cached prefix** rather than three competing
for 2.3 GB of headroom.

**Six tools is the ceiling.** The spike's naive run had four and produced a
misroute; six hardened ones scored 100% on selection. A seventh needs its own
evaluation run, not a hunch.

### What `search_children_by_concern` actually searches

Presenting concerns live in `ProblemEntry` (`clinical/models.py:342`) —
`description` (free text) and `category`. The resolver matches
`description__icontains` OR `category__icontains` against
`ProblemEntry.objects.filter(child__in=_visible_children(request),
resolved=False)`, and returns the distinct children.

**Open problems only.** A resolved problem is history, and a psychologist asking
"who has school refusal" means who has it now.

It returns **children**, not problem text — so a child appears in the list, but
another author's problem description is never rendered. That matters because
`ProblemEntry` is one of the two models the existing carry-history block does
not filter (a pre-existing gap noted in the parent spec's final review);
returning names rather than text keeps this tool clear of it.

### `get_child_summary` and the carry-history control

`Child.assignee_sees_history` (default `True`) hides a previous psychologist's
records from a newly assigned one. The parent spec's final review found the
pre-session brief reading past it; this tool has the identical exposure.

`get_child_summary` therefore reuses `_brief_only_author(child, user, role)` —
already in `assistant/views.py` — and filters recent remarks to the caller's own
when the flag is `False`. Without this, the chatbot becomes a way around a
confidentiality control the screens enforce.

It returns structured fields the frontend renders: first name, age, status,
assigned psychologist, recent remarks (filtered), and open care gaps. Never
model prose.

**Name resolution** searches `_visible_children` by `fullname__icontains`.
Zero matches returns "no child by that name in your caseload"; **multiple
matches return the list for the user to choose from** rather than guessing.

## The validator

`validate(tool, raw_args)` in `assistant/tools.py`. Each step exists because the
spike observed the failure, not because it might happen:

- **Normalize keys.** The model emitted `{"when: ": "today"}` — key including a
  colon and a trailing space. Strip punctuation and whitespace before lookup; a
  naive `args["when"]` raises `KeyError` and 500s the turn.
- **Coerce enum values through an alias table.** It returned `{"when": "bukas"}`,
  which is not in the enum at all. Table: `bukas → tomorrow`, `ngayon → today`,
  `kahapon → yesterday`. Deterministic, instant, free — and the single change
  that takes 91% to 100% on the measured set.
- **Reject unknown tools and missing required arguments** — fall through to the
  "I didn't follow that" response, never a guess.
- **Ignore anything resembling a scope argument.** No tool accepts one. A
  dropped or invented argument cannot widen a caller's view, because scope is
  never read from the model's output.

## Prompt assembly

Static-prefix-first, as the parent spec requires: system prompt, tool
definitions and few-shot examples are module constants, byte-identical on every
call; the user's question is appended last. Few-shot examples are worth 9 points
(82% → 91%) and cost nothing at runtime once the prefix is cached.

Tool descriptions are written in the user's vocabulary with explicit negatives
("…who they are seeing… Do NOT use this to search for children") — the change
that alone took tool selection from 77% to 100%.

**No per-request model options.** `run_job` already enforces this; each distinct
option set forces a model reload.

## Error handling

| Condition | Response |
|---|---|
| Assistant off, feature off, or runtime unreachable | 503 — the panel says "unavailable" |
| Question over 150 characters | 400 with a plain message |
| Model picks `answer_directly` | Fixed copy; no query runs |
| Unknown tool, or missing required argument | "I didn't follow that", plus what it can answer |
| Valid tool, empty result | "No children match" — an answer, not an error |
| Model returns prose instead of a tool call | Treated as `answer_directly` |

Failed calls still write an `AssistantJob` with `ok=False`, as `run_job` already
does.

## User interface

A docked panel mounted in `Shell` (`App.jsx:26`), available on every protected
route. Three states: idle, "Thinking…" (~5 s), result.

**The echo line is required, not decorative.** Before any result: *"Looking up:
active children · concern: school refusal."* This is the mitigation for the one
failure the spike could not eliminate — a silently dropped filter producing a
plausible wrong answer. If the model misheard, the user sees it.

Past answers remain on screen. The panel states **"English only"** (see below).

## Language

**English at launch.** The alias table maps a handful of Tagalog time words to
enum values, but that is a narrow fix, not comprehension:

- Free-text arguments do not translate. A Tagalog phrase in `concern` searches
  an English-language field and returns nothing — a failure that does not look
  like a language problem.
- Exactly **one** Tagalog sentence has been measured, four times. That is not
  evidence of support.

**Claiming Tagalog support requires its own evaluation run** — 12–15 realistic
Tagalog and Taglish questions through `ai_eval` — before the UI stops saying
"English only". Taglish (English clinical terms inside Tagalog sentences, which
is how people actually write here) may well perform better than pure Tagalog,
but that is a hypothesis, not a finding.

## Privacy

The architecture is the control. Because results never enter a prompt, the
entire clinical surface reaching the model is one question of at most 150
characters. A conventional chatbot that narrates its results would put case data
through the model on every turn; this one does not.

Two operational requirements:

- **`OLLAMA_HOST=127.0.0.1`.** Verified 2026-08-26: Ollama is currently
  listening on `0.0.0.0:11434` and `[::]:11434` — all interfaces, not loopback.
  Nothing clinical leaks from this directly (the model holds no data), but it is
  an unauthenticated service reachable from the local network, and it
  contradicts a claim `docs/CLOUD-DEPLOYMENT.md` makes. Document it in
  `docs/LOCAL-SETUP.md` alongside `OLLAMA_KEEP_ALIVE=-1` and
  `OLLAMA_NUM_PARALLEL=1`.
- **Logging carries no prompt content.** Verified: `LOGGING` in `settings.py`
  has a console handler only, no file handler, and nothing in the assistant logs
  prompt text. This design must not add any.

**What the audit stores, stated explicitly rather than left to happen quietly:**
`AssistantJob.input_ref` holds the user's question (which is why the cap is 150
characters — `input_ref` is `max_length=150`, so a valid question always fits
whole). `output_text` holds the tool call. A question can contain a child's
name. That text lives in the same database, under the same protections, as the
remarks it refers to — and having it is what makes the usage table and `ai_eval`
worth anything.

## Testing

Django tests with the client patched — no test may require a running Ollama:

- **Validator:** malformed keys, an unknown tool, missing required arguments,
  each alias-table entry, an out-of-enum value with no alias.
- **Resolvers:** each tool against real querysets, including the empty result.
- **Permission matrix:** a psychologist reaching only their own children; an
  administrator reaching all; `list_my_appointments` returning nothing for an
  administrator.
- **Carry-history:** `get_child_summary` on a child with
  `assignee_sees_history=False` excludes another author's remarks.
- **Name resolution:** zero matches, one match, several matches.
- **Prefix stability:** the static block is byte-identical across two different
  questions.
- **Degradation:** 503 with the assistant off, with the feature off, and with
  the runtime unreachable.
- **`answer_directly` returns fixed copy** — assert no model prose reaches the
  response.

**`manage.py ai_eval`** — the spike's case set as a permanent command, run
against real Ollama, printing per-case verdicts and a score. Routing accuracy
will regress the day someone adds a seventh tool; without a scoreboard nobody
notices.

## Migrations

One migration, and it is smaller than this spec first assumed. The per-feature
flags were removed on 26 Aug 2026 when the assistant became on-by-default, so
there is no `feature_chat` to add and `gate()` now takes no argument — the
chatbot sits behind the same single administrator switch as everything else.

The migration adds `"chat"` to `AssistantJob.TYPE_CHOICES`. That is all.

## Non-goals

No conversation memory. No retrieval, embeddings or pgvector. No second model
call to narrate results. No writes of any kind. No model-generated prose
anywhere in the chatbot. No hosted or cloud provider. No Tagalog claim until an
evaluation run supports one. No seventh tool without its own evaluation.
