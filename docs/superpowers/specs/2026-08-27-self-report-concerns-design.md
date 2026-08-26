# Self-report concerns

**Status:** design, approved in conversation 27 Aug 2026. Not built.

## Context

`seed_demo_data` builds three cohorts, and the note in CLAUDE.md says of the
third: *"whose self-reports drift toward distress while the case notes stay
reassuring. That last group is the point; it is what a divergence detector
would be built to find."* The data was written for a feature that does not
exist. This is that feature.

It is real in the data. One child, from the live local database:

| Date | Voice | Text |
|---|---|---|
| 27 Jun | Child | *"Minsan okay, minsan hindi. Depende sa araw."* |
| 17 Jun – 30 Jul | Psychologist | "Progressing as expected." · "Cooperative throughout." · "Adjusting well to the placement. Nothing to note." |
| **1 Aug** | **Child** | ***"Gusto ko na umuwi. Lagi akong umiiyak sa gabi."*** |
| 11 Aug | Psychologist | "Routine session. Nakangiti naman, participative." |
| 22 Aug | Psychologist | "Adjusting well to the placement. Nothing to note." |

The child said she cries every night. Eleven days later the note reads
"adjusting well… nothing to note."

**The words were never hidden.** `ChildProgressReport.jsx:304` already renders
them, collapsed behind an `Answers (3)` toggle, in a section separate from the
remarks. They were one click away from anyone who thought to look. Nobody did.
That is the actual failure this feature addresses: not missing data, but data
nobody had a reason to open.

## What it claims

**It is called self-report concerns, not a divergence detector.** The feature
was scoped to distress in the child's words alone. It never reads the
psychologist's notes and must never imply that it did.

The flag asserts exactly one thing: **this child said something worth reading.**

It does not assert that anyone missed anything, that the case is mishandled, or
that the child is at risk. Those are conclusions for a human who has read the
record. A system that flags a phrase has not read the record.

## What the data taught us

A spike on 27 Aug 2026 examined all 122 submitted self-reports. Three findings
changed the design; the fourth killed the measurement the spike was for.

### The demo data cannot measure recall

366 answer strings, **17 distinct**. `seed_demo_data` draws from a fixed pool.
Measuring a detector's recall against it measures the seeder's imagination.

No recall figure is claimed anywhere in this design, and none may be quoted
from demo data. Recall becomes knowable only when real children have used the
system — see **Tuning from real use**.

### The self-reports are not only Taglish — there is Ilocano

Three of the 17 strings:

```
Naimbag met. I can sleep at night now.
Adda met bassit nga problema but I don't want to say.
Mabutbuteng. I am scared but I don't tell them.
```

Two of those are distress. `mabutbuteng` — scared. `adda … problema` — there
is a problem. A Tagalog word list passes both.

This fits the agency: RACCO **1**, Ilocos Region, and the seeded surnames are
Ilocano (Bumanglag, Agpalza, Cariaga, Tabuena). CLAUDE.md records that "the
notes are Taglish", which holds for staff-authored notes. It is incomplete for
what children write about themselves.

### The strongest signal is invisible if you read answers alone

Every invite asks the same three questions. Two answers dominate:

| Answer | Count | Question |
|---|---|---|
| "Nobody" | 35 | *Who do you talk to when you are sad?* |
| "Ako lang" | 27 | *Who do you talk to when you are sad?* |

**62 of 122 reports say the child has no one to talk to when sad.** "Nobody" is
an unremarkable word on its own. It is distress only because of the question
above it.

**Therefore detection operates on the (question, answer) pair, never on answer
text alone.** A detector reading answers would miss the largest signal present.

## Detection

Two independent detectors. **Either firing raises the flag. Neither can clear
one.**

### The lexicon (always available)

A list of phrases in Tagalog, Ilocano and English, plus **question-specific
rules**. Concretely, one rule exists at launch: for *"Who do you talk to when
you are sad?"*, an answer meaning *no one* — "Nobody", "Ako lang", "Wala",
"Awan" — flags, while the same words answering the other two questions do not.
Rules are keyed to the question text, and an unrecognised question falls back
to phrase matching alone rather than failing.

Deterministic, sub-millisecond, no runtime dependency, and auditable: the flag
records which phrase fired, so a reviewer can see why.

It is the **floor**. If Ollama is down, swapped, or the model drifts, flagging
continues unchanged. A child-safety signal must not depend on a 3B model on a
laptop.

**The Ilocano entries need a speaker's review before launch.** The seed list is
drawn from phrases observed in the data plus a small number of high-confidence
terms. It was not written by an Ilocano speaker, and an invented entry is worse
than a missing one because it looks authoritative. Mark the list as reviewed
only once someone who speaks it has read it.

### The model (adds reach)

`qwen2.5:3b-instruct` classifies the (question, answer) pair. It exists to catch
phrasing nobody thought to list — precisely where Ilocano will hurt us.

It runs through the existing client seam, the shared generation lock, and the
audited job trail, exactly like every other assistant feature. Prompt assembly
is static-prefix-first, per the rule in CLAUDE.md.

**Its output can only add a flag.** It is never consulted about whether to
remove one, and its unavailability degrades to the lexicon silently and safely.

**Unmeasured, and stated as such:** the model's accuracy on Ilocano is unknown.
`qwen2.5:3b` was measured on Taglish, not on a low-resource Philippine
language, and there is no reason to assume the results transfer. This is why it
supplements the lexicon rather than replacing it.

## Storage

New model `SelfReportFlag` in `clinical`:

- the invite it came from, and the child (denormalised, indexed, for scoping)
- **a snapshot of the question and the answer** — editing a template later must
  not rewrite history
- which detector fired, and the matched phrase or the model's one-line reason
- acknowledgement: who reviewed it, when, and an optional note

Acknowledgement is not optional to build. Without it flags accumulate forever,
the list stops being read, and the feature becomes decoration.

## Timing

- **Lexicon runs synchronously on submission.** Instant.
- **The model runs in a background thread**, the pattern already used by
  `_start_prefetch_thread`.

A child submitting a self-report must never wait on a model call. The survey
endpoint is public and token-gated, reached from a child's own device.

`manage.py scan_self_reports` backfills existing records and is idempotent.

## Surfacing

**A new alert type in `compute_alerts()`** (`clinical/care_gaps.py`). That
places it on **Monitoring**, with no new screen and no new permission surface.
The chatbot answers about it for free through `list_care_gaps`.

**One consequence to note rather than bury:** the audience chosen for this
feature was *psychologist and administrator*. Monitoring is routed to
Administrator, **Staff** and Psychologist (`App.jsx`), so reusing it includes
Staff. That is not a new exposure — Staff already see every child's self-report
answers on the existing child page, and already see every care-gap alert. But
it is one role wider than was asked for, and it is a consequence of reuse
rather than a decision. If Staff should not see these flags, they need
filtering out explicitly, which is a small change but must be deliberate.

Alerts read persisted flags. No text analysis runs inside `compute_alerts`,
which is called on page load.

**On the child's page, a flagged answer is shown expanded, beside the recent
remarks** — not folded behind the existing toggle, and not in a separate
section from the notes it should be read against.

Unflagged reports stay visible as they are today. Since recall is unknown, this
is the part that actually protects the child: a missed report is unhighlighted,
never hidden.

## Carry-history

`Child.assignee_sees_history` is set by an administrator or staff member at
reassignment — never by a psychologist (`children/serializers.py:188`) — and its
label reads *"Carry this child's session history to the new psychologist
(they'll see prior records). Uncheck to give them a fresh start."*

**Self-reports are exempt from it.** The child's own words always reach the
psychologist currently responsible for her.

The reasoning, recorded because this was a deliberate decision and not a
default: the control exists to spare a new psychologist a colleague's prior
opinions, not to hide the child from the person now caring for her. A new
psychologist needs to know what happened before in order to act on it.

The counter-argument was considered and rejected: a self-report can itself be a
disclosure about a previous placement, and an agency might restrict it for
safeguarding reasons. That is a real risk and the reason this was escalated
rather than defaulted. The agency's decision is that awareness wins.

**The exception must be visible in the UI.** An administrator who unchecks
carry-history and then sees self-reports appear anyway must read that as
designed, not broken. The child's page states that self-reports are always
shown because they are the child's own words, not carried history.

### The psychologist's notes are unaffected

Stated explicitly so the exemption above is never misread as a change to case
notes. **Nothing in this design alters how notes are carried.** They keep
following `assignee_sees_history` exactly as they do today:

- **They carry by default.** The field defaults to `True`
  (`children/models.py:114`), so a newly assigned psychologist sees the full
  prior history unless someone deliberately unticks the box at reassignment.
- **They are never deleted.** The control is a read-time query filter
  (`clinical/reports_views.py:54`), not a deletion. Every remark persists with
  its author attached, and there is no deletion anywhere in the reassignment
  path. Tick the box again and the notes reappear intact.
- **So they remain available for future use** — including for a psychologist
  assigned years later, or for any administrator, who is never filtered.

The only way a note is hidden from anyone is an administrator choosing a fresh
start for one specific child, and even then it is hidden from that one
psychologist's view, not removed from the record.

## Privacy

Nothing leaves the machine. The model call goes to local Ollama, as every
assistant feature does. A commercial sentiment API was never considered: it
would mean transmitting distressed children's disclosures to a third party and
would put a processor in §6 for exactly the reason the `locations` app refuses
a live address API.

The child's words are already visible to Administrator, Staff and Psychologist
on existing screens. This feature does not widen who can see them — it changes
what gets noticed.

## Testing

Fixtures are written from **strings the live database actually contains**,
including the Ilocano ones. On 26 Aug a search feature shipped green because its
test invented fixture text that agreed with the assumption; that must not
recur — see the memory note `test-fixtures-must-use-real-vocabulary`.

Required cases:

- Each observed distress string flags, including all three Ilocano lines.
- **Each observed non-distress string does not flag** — "I feel safe. Ang bait
  ng nag-aalaga sa akin.", "Okay lang. I like the food and my bed.", "Masaya
  naman ako dito. May kaibigan na ako.", "Naimbag met. I can sleep at night
  now." Without these the lexicon can pass by flagging everything.
- "Nobody" and "Ako lang" flag against the isolation question and **do not flag**
  against the other two.
- A flag is scoped: one psychologist's flag never reaches another's Monitoring.
- Self-reports flag and display with `assignee_sees_history=False`.
- The model being unavailable does not reduce lexicon flagging.

`ai_eval` gains a feature scoring the model detector against hand-labelled
pairs, reporting misses as well as false alarms — the unmeasured half is the
half that breaks.

## Tuning from real use

The matched phrase is recorded on every flag, so the lexicon can be tuned from
what children actually write rather than from guesses. Two things make misses
discoverable:

1. Unflagged self-reports remain visible on the child's page.
2. A reviewer acknowledging a flag can note that it was unhelpful.

Adding a phrase must stay a one-line change to a list.

## Non-goals

- **No severity ranking or scores.** `ResultEntry` says *"No computed scores,
  ever."* This respects that.
- **No assessment of any psychologist's work.** The notes are never read.
- **No automatic notification** — no email, no SMS. Flags appear where people
  already look.
- **No conclusion about risk.** The feature surfaces words; humans judge them.

## What is not claimed

- No recall or precision figure. Demo data cannot produce one and real data does
  not exist yet.
- No claim that the model handles Ilocano. That is unmeasured.
- No claim that the lexicon is complete. It will miss phrasing, which is why the
  model supplements it and why unflagged reports stay visible.
