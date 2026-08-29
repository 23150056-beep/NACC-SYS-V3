# Assistant chat: coverage, time filtering and a second door

**Date:** 29 Aug 2026
**Status:** design, approved for planning
**Supersedes nothing.** Extends `2026-08-26-assistant-chatbot-design.md`, whose
architecture is unchanged: the model's only output is a tool name and its
arguments, the server runs the queryset, and scope always comes from
`request.user`.

## Why

The chatbot answers five questions well and refuses everything else with one
fixed sentence. Three problems follow from that, and a fourth was found while
writing this document.

1. **The refusal is indiscriminate.** `_resolve_direct` ignores the `reason`
   the model supplies, so "salamat po" is answered with the same capability
   lecture as an unanswerable question.
2. **Self-reports have no conversational surface.** `SelfReportFlag` exists to
   surface a child's own words about distress. It is the highest-stakes data in
   the system and the chatbot cannot reach it.
3. **Time filtering is four near-term values.** `today`, `tomorrow`,
   `this_week`, `next_week` — no past at all, no month, no year.
4. **`kahapon` is aliased to `today`.** *Kahapon* means yesterday. Asking
   "sino ang nakita ko kahapon?" returns today's appointments, confidently,
   with nothing to indicate the question was reinterpreted. This is the exact
   failure the design exists to prevent, and it was introduced by aliasing
   around a missing capability rather than declining.

## Scope

**In:** period vocabulary and the `kahapon` fix; a reason- and role-aware
fallback; child-name matching that survives how people type; one new tool for
self-report flags; a quick-action entry point to the existing panel.

**Out, deliberately:**

- **Conversation history.** "And tomorrow?" is the largest usability gap, and
  supporting it means state after the cached prefix — the decision that costs
  ~17s a call. A client-side mechanism (resend the previous tool with one
  argument changed, so the model is never asked to remember) is the likely
  answer and deserves its own design.
- **Admin and staff tools** — people counts, unassigned children, availability,
  records gaps. Wanted, and the reason this is phase B: the eval baseline has
  to exist before the registry doubles.
- **Period-filtered census counts** ("how many cases closed this year"). The
  `PERIODS` table is built here and reused there.

## 1. Periods

One table replaces `_WINDOWS`, used by every time-aware tool.

| Grain | Values |
|---|---|
| Day | `today`, `yesterday`, `tomorrow` |
| Week | `this_week`, `last_week`, `next_week` |
| Month | `this_month`, `last_month` |
| Year | `this_year`, `last_year` |

**Week, month and year are calendar-aligned; days are offsets.** `_WINDOWS`
today is rolling — `this_week` means today through +7 days. That reading does
not survive `last_month` or `this_year`, and mixing the two would have "this
week" and "this month" answering on different logic. This changes what
`this_week` returns; that is intended and must be in the eval cases.

**The week starts on Sunday**, because `Schedule.jsx` builds its calendar with
date-fns `startOfWeek` under the `en-US` locale, and the chatbot must agree
with the screen the user is looking at — the same principle `list_care_gaps`
already follows. (The availability editor's `WEEKDAYS` array lists Monday
first. That inconsistency predates this work and is not fixed here.)

Aliases grow to match: `kahapon`→`yesterday` (corrected), `ngayong buwan`→
`this_month`, `nakaraang buwan`→`last_month`, `ngayong taon`→`this_year`,
`nakaraang taon`→`last_year`, and the English equivalents.

**The Tagalog aliases need a native speaker's review before release**, the same
discipline `LEXICON_REVIEWED` applies to Ilocano. They are written by the same
process that produced the `kahapon` error.

### Appointment status depends on the period, not on a past/future flag

`_resolve_appointments` filters `status=SCHEDULED`. For a past period that
returns nothing, because yesterday's appointments are `COMPLETED`, `NO_SHOW` or
`CANCELLED` — the same confident-empty failure in a new costume.

"Past periods drop the filter" is not sufficient, because `this_week`,
`this_month` and `this_year` contain both. Asked on a Wednesday, "what did I do
this week" would hide Monday's completed sessions. The rule is therefore:

| Period | Statuses returned |
|---|---|
| Contains no past days (`tomorrow`, `next_week`) | `SCHEDULED` only |
| Contains any past day (`today`, `yesterday`, `this_week`, `last_week`, `this_month`, `last_month`, `this_year`, `last_year`) | `SCHEDULED`, `COMPLETED`, `NO_SHOW` |

`CANCELLED` is excluded everywhere: a cancelled appointment is not a session,
and listing it under "who am I seeing" would be a different kind of wrong
answer. `today` counts as containing a past day — a session completed this
morning belongs in the answer.

The panel's existing `appointments` renderer gains a status label. No new
result `kind`.

## 2. A fallback that answers

`_resolve_direct` becomes a server-side builder keyed on `(reason, role)`:

- `greeting_or_closing` — a short acknowledgement. No capability list.
- `general_knowledge` / `unsupported` — what **this role** can ask, listing only
  what it can reach. A psychologist is never told about user management.

**Role-awareness costs nothing.** It happens in the resolver, which the model
never sees. `CHAT_SYSTEM` stays byte-identical, so the prefix cache stays warm.

`CHAT_SYSTEM` currently asserts "The signed-in user is a psychologist", which is
wrong for two of three roles. It is left alone here: making it role-dependent
would fork the cached prefix three ways. Phase C.

A server-side detector for action requests ("book Ana for Friday", "i-reset mo
ang password") routes to a distinct refusal that says where to do it instead.
Like `correct_obvious_misroute`, it only ever changes refusal wording — it
cannot make the assistant assert anything, so it cannot introduce a wrong
answer.

Its `action_request` reason is **server-side only and is not added to the
model-facing enum**. The guard constructs its `ToolCall` directly, exactly as
`correct_obvious_misroute` already does, so `validate()` never sees the value
and the tool schema the model reads does not grow. `_resolve_direct` handles
the extra reason; `ollama_payload()` output is unchanged.

## 3. Child names as people type them

`fullname__icontains="ana reyes"` finds nothing when the record says
"Anabelle Suguitan". Reuse `_search_words` — the word matching already proven
for concerns, and for the same reason — after stripping honorifics (`si`, `ni`,
`po`, `ang`). Match any significant word, then use the paths that already
exist: one match renders the summary, several render the disambiguation list,
none renders the not-found state.

No frontend change. It feeds UI states the panel already has.

## 4. `list_self_report_flags`

| | |
|---|---|
| **Schema** | `state`: `unreviewed` (default) \| `all`, optional. `period`: optional, from §1. |
| **Scope** | `_scope(request)`, identical to every other tool. |
| **Returns** | child name and id, question, the child's answer, date, reviewed state. |
| **Kind** | `self_report_flags` — the one new panel renderer. |

Both arguments are optional. `reason` taught this lesson: a required argument
the model omits once in 28 turns is a failed turn.

The child's own answer **is** included. The child report screen already shows
these expanded above the case notes, so chat is consistent rather than more
exposing, and a flag without the words is not actionable. Self-reports are
exempt from the carry-history control — the child's own words are not a
colleague's prior opinions — so no author filtering applies.

The result asserts what the model asserts: this child said something worth
reading. Never that anyone missed anything.

## 5. Quick-action entry point

The panel's `open` is local state; quick actions only `navigate(to)`. Neither
can reach the other.

A small `AssistantContext` — matching `Auth`, `Toast` and `Activity` — exposes
`openAssistant()`. `AssistantPanel` reads `open` from it instead of `useState`.
The quick-actions array gains support for an `onClick` action alongside `to`.

This is **one more door to the same assistant**, not a second chatbot: same
endpoint, same panel, same stateless session. It opens showing example
questions, because a user arriving from a button has typed nothing and an empty
panel gives no hint what is askable. Those examples come from the same
role-aware source as §2, so there is one answer to "what can I ask" and not two.

Icon: `bot`. `sparkles` is already the Quick actions header icon and repeating
it makes the row read as decoration.

## Measurement

`ai_eval --feature chat` gains cases, English and Tagalog:

- every period value, including `kahapon` specifically
- greetings, asserting the reply is **not** the capability list
- capability questions, per role
- partial and misspelled child names
- self-report questions, with and without a period

**Gate: routing accuracy must not fall below the current 55/55 baseline.** The
eval scores whether the answer came back non-empty as well as whether the
routing was right — the unmeasured half is the half that broke when the concern
search shipped returning nothing for every real question.

If the gate fails, the period vocabulary shrinks rather than ships. Going from
4 enum values to 10 is the single largest routing risk here, and "how many
children this year" now has a plausible wrong route into the appointments tool.

Unit test fixtures use vocabulary read from the live database, never invented.

## Files

| File | Change |
|---|---|
| `backend/assistant/tools.py` | `PERIODS`, aliases, three resolvers, one registry entry |
| `backend/assistant/prompts.py` | examples only; prefix stays static |
| `backend/assistant/tests/` | validator, resolvers, refusal wording |
| `frontend/src/context/AssistantContext.jsx` | new |
| `frontend/src/components/AssistantPanel.jsx` | context, new renderer, status label |
| `frontend/src/pages/Dashboard.jsx` | quick action |
| chat eval cases | new periods, greetings, names, flags |

## Risks

1. **Routing accuracy** — mitigated by the eval gate, which can reject the
   vocabulary.
2. **`this_week` changes meaning** — deliberate, and the only alternative is
   week and month answering on different logic.
3. **Tagalog aliases unreviewed** — gates release, not building. `kahapon` is
   the proof that this is not theoretical.
