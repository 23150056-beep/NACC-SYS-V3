# Assistant Chat Coverage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the chat assistant periods down to the year, a fallback that
distinguishes a greeting from an unanswerable question, child names matched the
way people type them, self-report flags reachable by asking, and a quick-action
door into the panel that already exists.

**Architecture:** Unchanged from the chatbot's original design. The model's only
output is a tool name and its arguments; the server runs the queryset and
returns a plain dict the panel renders; scope always comes from `request.user`.
Everything added here is server-side, so no new answer can be invented by the
model. Role-awareness lives in a resolver the model never sees, which is why
`prompts.CHAT_SYSTEM` can stay byte-identical and keep the prefix cache warm.

**Tech Stack:** Django 5 + DRF, SQLite locally, React 18 + Vite, Ollama
(`qwen2.5:3b-instruct`) locally / Cloudflare Workers AI hosted.

**Spec:** `docs/superpowers/specs/2026-08-29-assistant-chat-coverage-design.md`

## Global Constraints

- **The week starts on Sunday.** `Schedule.jsx` builds its calendar with
  date-fns `startOfWeek` under the `en-US` locale; the chatbot must agree with
  the screen the user is comparing against.
- **`CANCELLED` appointments are excluded from every period.** A cancelled
  appointment is not a session.
- **`action_request` is server-side only and never enters the model-facing
  enum.** The guard constructs its `ToolCall` directly, as
  `correct_obvious_misroute` already does; `ollama_payload()` output must not
  change.
- **`prompts.CHAT_SYSTEM` must remain identical on every call.** It may be
  edited once (adding examples); it must never become role-dependent.
- **Both new tool arguments are optional.** A required argument the model omits
  once in 28 turns is a failed turn — the lesson `reason` already taught.
- **Test fixtures use vocabulary read from the live database, never invented.**
- **Eval gate:** `ai_eval --feature chat` routing accuracy must not fall below
  the current 55/55 baseline. If it does, the period vocabulary shrinks rather
  than ships.
- **Commits are authored and committed by `Reynold <jreynoldcanedo@gmail.com>`.**
  No Claude attribution, no `Co-Authored-By`, no model name in any commit
  message or code comment.

---

### Task 1: Period vocabulary and the `kahapon` fix

Pure date arithmetic and the alias table. No database, no model. This is the
foundation every later task consumes.

**Files:**
- Modify: `backend/assistant/tools.py` (replace `_WINDOWS`, extend `ALIASES`,
  extend the `when` enum in `REGISTRY["list_my_appointments"]`)
- Test: `backend/assistant/tests/test_tools.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `tools.PERIODS: tuple[str, ...]` — the ten enum values, in order.
  - `tools.FUTURE_ONLY: set[str]` — `{"tomorrow", "next_week"}`.
  - `tools.period_range(period: str, today: datetime.date | None = None) -> tuple[date, date]`
    returning `(start, end)` with **end exclusive**. Raises `KeyError` on an
    unknown period.

- [ ] **Step 1: Write the failing tests**

Add to `backend/assistant/tests/test_tools.py`:

```python
from datetime import date

from assistant import tools


class PeriodRangeTest(SimpleTestCase):
    """Weeks start on Sunday, matching Schedule.jsx. End is exclusive."""

    # A Wednesday, so week boundaries are visible in both directions.
    WED = date(2026, 8, 26)

    def test_today_is_one_day(self):
        self.assertEqual(tools.period_range("today", self.WED),
                         (date(2026, 8, 26), date(2026, 8, 27)))

    def test_yesterday_is_the_day_before(self):
        self.assertEqual(tools.period_range("yesterday", self.WED),
                         (date(2026, 8, 25), date(2026, 8, 26)))

    def test_tomorrow_is_the_day_after(self):
        self.assertEqual(tools.period_range("tomorrow", self.WED),
                         (date(2026, 8, 27), date(2026, 8, 28)))

    def test_this_week_starts_on_the_preceding_sunday(self):
        # 26 Aug 2026 is a Wednesday; the Sunday before is the 23rd.
        self.assertEqual(tools.period_range("this_week", self.WED),
                         (date(2026, 8, 23), date(2026, 8, 30)))

    def test_a_sunday_starts_its_own_week(self):
        self.assertEqual(tools.period_range("this_week", date(2026, 8, 23)),
                         (date(2026, 8, 23), date(2026, 8, 30)))

    def test_last_week_and_next_week(self):
        self.assertEqual(tools.period_range("last_week", self.WED),
                         (date(2026, 8, 16), date(2026, 8, 23)))
        self.assertEqual(tools.period_range("next_week", self.WED),
                         (date(2026, 8, 30), date(2026, 9, 6)))

    def test_this_month_and_last_month(self):
        self.assertEqual(tools.period_range("this_month", self.WED),
                         (date(2026, 8, 1), date(2026, 9, 1)))
        self.assertEqual(tools.period_range("last_month", self.WED),
                         (date(2026, 7, 1), date(2026, 8, 1)))

    def test_month_arithmetic_crosses_the_year(self):
        self.assertEqual(tools.period_range("this_month", date(2026, 12, 5)),
                         (date(2026, 12, 1), date(2027, 1, 1)))
        self.assertEqual(tools.period_range("last_month", date(2026, 1, 5)),
                         (date(2025, 12, 1), date(2026, 1, 1)))

    def test_this_year_and_last_year(self):
        self.assertEqual(tools.period_range("this_year", self.WED),
                         (date(2026, 1, 1), date(2027, 1, 1)))
        self.assertEqual(tools.period_range("last_year", self.WED),
                         (date(2025, 1, 1), date(2026, 1, 1)))

    def test_an_unknown_period_raises(self):
        with self.assertRaises(KeyError):
            tools.period_range("last_fortnight", self.WED)


class KahaponMeansYesterdayTest(SimpleTestCase):
    """Regression. It was aliased to `today`, so "sino ang nakita ko kahapon?"
    answered with today's appointments and said nothing about it."""

    def test_kahapon_maps_to_yesterday(self):
        call = tools.validate("list_my_appointments", {"when": "kahapon"})
        self.assertTrue(call.ok, call.error)
        self.assertEqual(call.args["when"], "yesterday")

    def test_month_and_year_words_map(self):
        for word, expected in [("ngayong buwan", "this_month"),
                               ("nakaraang buwan", "last_month"),
                               ("ngayong taon", "this_year"),
                               ("nakaraang taon", "last_year"),
                               ("last week", "last_week")]:
            call = tools.validate("list_my_appointments", {"when": word})
            self.assertTrue(call.ok, f"{word}: {call.error}")
            self.assertEqual(call.args["when"], expected, word)

    def test_every_period_is_accepted_by_the_validator(self):
        for period in tools.PERIODS:
            call = tools.validate("list_my_appointments", {"when": period})
            self.assertTrue(call.ok, f"{period}: {call.error}")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && .venv/Scripts/python.exe manage.py test assistant.tests.test_tools -v 2`
Expected: FAIL — `AttributeError: module 'assistant.tools' has no attribute 'period_range'`

- [ ] **Step 3: Implement the period table**

In `backend/assistant/tools.py`, add near the top (after the `import re` line,
adding `from datetime import date, timedelta`), and **delete `_WINDOWS`**:

```python
# Periods. Weeks, months and years are calendar-aligned; days are offsets.
# Rolling windows ("today through +7") do not survive `last_month`, and mixing
# the two would have "this week" and "this month" answering on different logic.
PERIODS = ("today", "yesterday", "tomorrow",
           "this_week", "last_week", "next_week",
           "this_month", "last_month",
           "this_year", "last_year")

# Periods that contain no past day. Everything else contains one — `today`
# included, because a session completed this morning belongs in the answer.
FUTURE_ONLY = {"tomorrow", "next_week"}


def _week_start(day):
    """The Sunday on or before `day`.

    Sunday because Schedule.jsx builds its calendar with date-fns startOfWeek
    under the en-US locale, and the chatbot must agree with the screen the user
    is looking at. Python's weekday() is Monday=0..Sunday=6, so the number of
    days since Sunday is (weekday() + 1) % 7.
    """
    return day - timedelta(days=(day.weekday() + 1) % 7)


def _month_start(day):
    return day.replace(day=1)


def _next_month(first):
    return date(first.year + (first.month == 12),
                1 if first.month == 12 else first.month + 1, 1)


def _previous_month(first):
    return date(first.year - (first.month == 1),
                12 if first.month == 1 else first.month - 1, 1)


def period_range(period, today=None):
    """(start, end) for a period name. End is EXCLUSIVE.

    `today` is injectable so tests can pin a weekday instead of depending on
    the day the suite happens to run.
    """
    if today is None:
        from django.utils import timezone
        today = timezone.localdate()

    if period == "today":
        return today, today + timedelta(days=1)
    if period == "yesterday":
        return today - timedelta(days=1), today
    if period == "tomorrow":
        return today + timedelta(days=1), today + timedelta(days=2)

    week = _week_start(today)
    if period == "this_week":
        return week, week + timedelta(days=7)
    if period == "last_week":
        return week - timedelta(days=7), week
    if period == "next_week":
        return week + timedelta(days=7), week + timedelta(days=14)

    month = _month_start(today)
    if period == "this_month":
        return month, _next_month(month)
    if period == "last_month":
        return _previous_month(month), month

    if period == "this_year":
        return date(today.year, 1, 1), date(today.year + 1, 1, 1)
    if period == "last_year":
        return date(today.year - 1, 1, 1), date(today.year, 1, 1)

    raise KeyError(period)
```

- [ ] **Step 4: Extend the alias table**

Replace the `"when"` block inside `ALIASES` with:

```python
    "when": {
        "ngayon": "today", "ngayong araw": "today", "today": "today",
        # Regression: this was mapped to "today". Kahapon is yesterday, and
        # aliasing around a missing period produced a confidently wrong answer.
        "kahapon": "yesterday", "yesterday": "yesterday",
        "bukas": "tomorrow", "tomorrow": "tomorrow",
        "ngayong linggo": "this_week", "this week": "this_week",
        "nakaraang linggo": "last_week", "noong isang linggo": "last_week",
        "last week": "last_week",
        "susunod na linggo": "next_week", "next week": "next_week",
        "ngayong buwan": "this_month", "this month": "this_month",
        "nakaraang buwan": "last_month", "noong isang buwan": "last_month",
        "last month": "last_month",
        "ngayong taon": "this_year", "this year": "this_year",
        "nakaraang taon": "last_year", "noong isang taon": "last_year",
        "last year": "last_year",
    },
```

Then widen the enum in `REGISTRY["list_my_appointments"]["schema"]`:

```python
        "schema": {"when": {"enum": list(PERIODS), "required": True}},
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd backend && .venv/Scripts/python.exe manage.py test assistant.tests.test_tools -v 2`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/assistant/tools.py backend/assistant/tests/test_tools.py
git commit -m "Give the assistant periods, and make kahapon mean yesterday

kahapon was aliased to today, so a question about yesterday was answered
with today's appointments and nothing said the question had been
reinterpreted. The alias existed because there was no past period to map
to; there are now ten, calendar-aligned for week, month and year.

Weeks start on Sunday because that is what Schedule.jsx shows, and the
chatbot must agree with the screen being compared against."
```

---

### Task 2: Appointments honour the period and its statuses

**Files:**
- Modify: `backend/assistant/tools.py` (`_resolve_appointments`)
- Test: `backend/assistant/tests/test_tool_resolvers.py`

**Interfaces:**
- Consumes: `tools.period_range`, `tools.FUTURE_ONLY` (Task 1).
- Produces: the `appointments` result dict gains a `status` key per item —
  `{"kind": "appointments", "when": str, "items": [{"child": str, "when": str,
  "purpose": str, "status": str}]}`. Task 6 renders `status`.

- [ ] **Step 1: Write the failing tests**

Add to `backend/assistant/tests/test_tool_resolvers.py`, inside
`AppointmentsResolverTest`:

```python
    def _appt_with(self, child, psychologist, days, status):
        appt = self._appt(child, psychologist, days=days)
        appt.status = status
        appt.save(update_fields=["status"])
        return appt

    def test_yesterday_returns_completed_sessions(self):
        # The confident-empty failure: filtering to SCHEDULED means a past
        # period always answers "nothing", because yesterday's work is done.
        self._appt_with(self.mine, self.psy, -1, Appointment.COMPLETED)
        out = self._resolve(self.psy, "list_my_appointments", {"when": "yesterday"})
        self.assertEqual(len(out["items"]), 1)
        self.assertEqual(out["items"][0]["status"], Appointment.COMPLETED)

    def test_a_no_show_is_returned_for_a_past_period(self):
        self._appt_with(self.mine, self.psy, -1, Appointment.NO_SHOW)
        out = self._resolve(self.psy, "list_my_appointments", {"when": "yesterday"})
        self.assertEqual(len(out["items"]), 1)

    def test_a_cancelled_appointment_is_never_returned(self):
        self._appt_with(self.mine, self.psy, -1, Appointment.CANCELLED)
        out = self._resolve(self.psy, "list_my_appointments", {"when": "yesterday"})
        self.assertEqual(out["items"], [])

    def test_a_future_period_returns_only_scheduled(self):
        self._appt_with(self.mine, self.psy, 1, Appointment.COMPLETED)
        self._appt_with(self.theirs, self.psy, 1, Appointment.SCHEDULED)
        out = self._resolve(self.psy, "list_my_appointments", {"when": "tomorrow"})
        self.assertEqual([i["status"] for i in out["items"]],
                         [Appointment.SCHEDULED])

    def test_this_week_spans_both_directions(self):
        # A week containing today holds finished work and upcoming work. Asked
        # on a Wednesday, "what have I got this week" must show Monday's
        # completed session as well as Friday's booking.
        start, end = tools.period_range("this_week")
        today = timezone.localdate()
        if start < today:                      # a past day exists in this week
            self._appt_with(self.mine, self.psy,
                            (start - today).days, Appointment.COMPLETED)
        self._appt_with(self.theirs, self.psy, 0, Appointment.SCHEDULED)
        out = self._resolve(self.psy, "list_my_appointments", {"when": "this_week"})
        self.assertGreaterEqual(len(out["items"]), 1)

    def test_a_month_period_resolves(self):
        self._appt_with(self.mine, self.psy, 0, Appointment.COMPLETED)
        out = self._resolve(self.psy, "list_my_appointments", {"when": "this_month"})
        self.assertEqual(len(out["items"]), 1)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && .venv/Scripts/python.exe manage.py test assistant.tests.test_tool_resolvers -v 2`
Expected: FAIL — `KeyError: 'yesterday'` from the deleted `_WINDOWS`, and
`KeyError: 'status'` on the item dicts.

- [ ] **Step 3: Rewrite the resolver**

Replace `_resolve_appointments` in `backend/assistant/tools.py` entirely:

```python
def _resolve_appointments(request, args):
    from django.utils import timezone
    from scheduling.models import Appointment

    period = args["when"]
    start, end = period_range(period)

    # A period with no past day is a plan, so only what is still going to
    # happen belongs in it. Any other period has finished work in it, and
    # hiding that answers "what did I do this week" with silence. CANCELLED is
    # excluded either way: a cancelled appointment is not a session.
    statuses = ([Appointment.SCHEDULED] if period in FUTURE_ONLY
                else [Appointment.SCHEDULED, Appointment.COMPLETED,
                      Appointment.NO_SHOW])

    appts = (Appointment.objects
             .filter(psychologist=request.user, status__in=statuses,
                     start__date__gte=start, start__date__lt=end)
             .select_related("child").order_by("start"))
    return {"kind": "appointments", "when": period, "items": [
        {"child": a.child.fullname,
         "when": timezone.localtime(a.start).strftime("%a %d %b, %H:%M"),
         "purpose": a.get_purpose_display(),
         "status": a.status} for a in appts]}
```

Update the tool's `echo` so a period reads naturally:

```python
        "echo": lambda a: f"Looking up: your appointments {a['when'].replace('_', ' ')}",
```

(unchanged — `this_month` already renders as "this month".)

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && .venv/Scripts/python.exe manage.py test assistant.tests.test_tool_resolvers -v 2`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/assistant/tools.py backend/assistant/tests/test_tool_resolvers.py
git commit -m "Answer a past period with the work that actually happened

Filtering to SCHEDULED meant every past period answered 'nothing',
because yesterday's appointments are completed by then — the same
confident-empty failure the concern search had. Status now follows
whether the period contains a past day, which this_week and this_month
both do. Cancelled appointments stay out: a cancellation is not a
session."
```

---

### Task 3: A fallback that distinguishes a greeting from a refusal

**Files:**
- Modify: `backend/assistant/tools.py` (`DIRECT_REPLY` → builders,
  `_resolve_direct`, new `correct_action_request`)
- Modify: `backend/assistant/views.py:517` (call the new guard)
- Test: `backend/assistant/tests/test_tool_resolvers.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces:
  - `tools.correct_action_request(question: str, call: ToolCall) -> ToolCall`
  - `tools.capability_text(role: str | None) -> str`
  - `tools.capability_examples(role: str | None) -> list[str]`
  - the `message` result dict gains `reason`, and its `text` varies by
    `(reason, role)`. Shape is unchanged: `{"kind": "message", "reason": str,
    "text": str}` — the panel already renders it, so no frontend change.

  `capability_text` and `capability_examples` are public because Task 7 serves
  them over HTTP. There must be exactly one answer to "what can I ask", not a
  server one and a hardcoded frontend one.

- [ ] **Step 1: Write the failing tests**

Add to `backend/assistant/tests/test_tool_resolvers.py`:

```python
class DirectReplyTest(ResolverTestBase):
    """A greeting is not an unanswerable question, and a psychologist is not
    an administrator. Both distinctions are made server-side, so the model
    never has to be told about roles and the cached prefix never forks."""

    def test_a_greeting_is_not_answered_with_a_capability_list(self):
        out = self._resolve(self.psy, "answer_directly",
                            {"reason": "greeting_or_closing"})
        self.assertEqual(out["kind"], "message")
        self.assertNotIn("can't answer", out["text"].lower())
        self.assertNotIn("cannot answer", out["text"].lower())

    def test_an_unsupported_question_lists_what_this_role_can_ask(self):
        out = self._resolve(self.psy, "answer_directly", {"reason": "unsupported"})
        self.assertIn("caseload", out["text"].lower())

    def test_a_psychologist_is_never_offered_user_management(self):
        out = self._resolve(self.psy, "answer_directly", {"reason": "unsupported"})
        self.assertNotIn("user account", out["text"].lower())

    def test_an_administrator_gets_a_different_list(self):
        mine = self._resolve(self.psy, "answer_directly", {"reason": "unsupported"})
        theirs = self._resolve(self.admin, "answer_directly", {"reason": "unsupported"})
        self.assertNotEqual(mine["text"], theirs["text"])

    def test_a_missing_reason_still_answers(self):
        # `reason` is optional; the model dropped it once in 28 turns.
        out = self._resolve(self.psy, "answer_directly", {})
        self.assertTrue(out["text"])


class ActionRequestGuardTest(SimpleTestCase):
    """The guard only ever changes refusal wording. It cannot make the
    assistant assert anything, so it cannot introduce a wrong answer."""

    def _guarded(self, question, tool="answer_directly", args=None):
        call = tools.ToolCall(tool=tool, args=args or {})
        return tools.correct_action_request(question, call)

    def test_a_booking_request_is_recognised(self):
        call = self._guarded("book Ana for Friday")
        self.assertEqual(call.args["reason"], "action_request")

    def test_a_tagalog_action_request_is_recognised(self):
        call = self._guarded("i-reset mo ang password ni Paul")
        self.assertEqual(call.args["reason"], "action_request")

    def test_a_question_about_the_schedule_is_left_alone(self):
        call = self._guarded("what is my schedule today?")
        self.assertNotEqual(call.args.get("reason"), "action_request")

    def test_it_never_touches_a_data_tool(self):
        call = self._guarded("book Ana for Friday", tool="list_my_appointments",
                             args={"when": "today"})
        self.assertEqual(call.tool, "list_my_appointments")
        self.assertEqual(call.args, {"when": "today"})

    def test_action_request_is_not_in_the_model_facing_schema(self):
        payload = tools.ollama_payload()
        direct = next(t for t in payload
                      if t["function"]["name"] == "answer_directly")
        enum = direct["function"]["parameters"]["properties"]["reason"]["enum"]
        self.assertNotIn("action_request", enum)
```

Add `SimpleTestCase` to the imports at the top of the file:

```python
from django.test import SimpleTestCase, TestCase
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && .venv/Scripts/python.exe manage.py test assistant.tests.test_tool_resolvers -v 2`
Expected: FAIL — `AttributeError: module 'assistant.tools' has no attribute 'correct_action_request'`

- [ ] **Step 3: Replace `DIRECT_REPLY` with role-aware builders**

In `backend/assistant/tools.py`, delete the `DIRECT_REPLY` constant and add:

```python
# What each role can actually ask, in its own words. Built here rather than in
# the prompt because the model never sees it: role-awareness therefore costs
# nothing, and CHAT_SYSTEM stays byte-identical so the prefix cache stays warm.
_CAN_ASK = {
    "Psychologist": (
        "your schedule, how many children are in your caseload, children with "
        "a particular concern, a summary of one child, who needs follow-up, "
        "and which children have flagged something in their own words"),
    "Administrator": (
        "the agency's schedule, how many children the agency is handling, "
        "children with a particular concern, a summary of one child, who needs "
        "follow-up, and which children have flagged something in their own "
        "words"),
    "Staff": (
        "the schedule, how many children the agency is handling, children with "
        "a particular concern, a summary of one child, and who needs "
        "follow-up"),
}
_CAN_ASK_DEFAULT = _CAN_ASK["Psychologist"]

# Shown in the empty panel. Questions, not features — someone who arrives by
# clicking a button has typed nothing and needs a starting point, not a menu.
_EXAMPLES = {
    "Psychologist": ["Who am I seeing today?",
                     "How many children do I have?",
                     "Who flagged something worrying?",
                     "Who needs follow-up?"],
    "Administrator": ["Who needs follow-up?",
                      "Who flagged something worrying?",
                      "Any children with anxiety?",
                      "What was scheduled last week?"],
    "Staff": ["Who needs follow-up?",
              "Any children with anxiety?",
              "What's on this week?",
              "Tell me about a child by name"],
}

GREETING_REPLY = "Hello — what would you like to look up?"

ACTION_REPLY = (
    "I can look things up, but I can't change anything. Bookings, records and "
    "accounts are edited on their own screens.")


def capability_text(role):
    """One sentence naming what this role can ask. Public because the panel
    serves it too — there must not be a server answer and a frontend one."""
    return f"You can ask me about {_CAN_ASK.get(role, _CAN_ASK_DEFAULT)}."


def capability_examples(role):
    return list(_EXAMPLES.get(role, _EXAMPLES["Psychologist"]))


def _resolve_direct(request, args):
    from assistant.views import _role

    reason = args.get("reason", "unsupported")
    if reason == "greeting_or_closing":
        text = GREETING_REPLY
    elif reason == "action_request":
        text = ACTION_REPLY
    else:
        text = capability_text(_role(request))
    return {"kind": "message", "reason": reason, "text": text}
```

- [ ] **Step 4: Add the action-request guard**

Add below `correct_obvious_misroute` in the same file:

```python
# Imperatives, not topics. "schedule" is absent on purpose — it appears in
# "what is my schedule today?", which is a question this assistant answers.
_ACTION_VERBS = (
    "book", "cancel", "create", "add", "delete", "remove", "reset", "update",
    "edit", "assign", "reassign", "upload", "send", "approve", "deactivate",
    "i-book", "i-cancel", "i-reset", "i-update", "i-assign", "i-delete",
    "magdagdag", "magbook", "burahin", "palitan", "tanggalin", "idagdag",
)


def correct_action_request(question, call):
    """Say "I can't change anything" instead of "I can't answer that".

    Only ever rewrites the reason on a call the model already routed to
    answer_directly, so — like correct_obvious_misroute — it can make the
    assistant decline differently and can never make it assert anything.
    """
    if not call.ok or call.tool != "answer_directly":
        return call
    words = _PUNCT.sub(" ", str(question or "").lower()).split()
    if words and words[0] in _ACTION_VERBS:
        return ToolCall(tool="answer_directly",
                        args={"reason": "action_request"}, echo="")
    return call
```

- [ ] **Step 5: Wire the guard into the ask view**

In `backend/assistant/views.py`, directly after the existing line 517
`call = tools.correct_obvious_misroute(question, call)`, add:

```python
        call = tools.correct_action_request(question, call)
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `cd backend && .venv/Scripts/python.exe manage.py test assistant.tests.test_tool_resolvers assistant.tests.test_ask -v 2`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add backend/assistant/tools.py backend/assistant/views.py backend/assistant/tests/test_tool_resolvers.py
git commit -m "Stop answering salamat with a list of features

One fixed sentence served greetings, unanswerable questions and requests
to change something alike, and it named capabilities the asker might not
even have. The reply is now built from the reason and the role, both on
the server — the model is never told about roles, so CHAT_SYSTEM stays
byte-identical and the prefix cache stays warm.

The action-request guard follows correct_obvious_misroute exactly: it
rewrites a refusal's wording and can never make the assistant assert
anything. Its reason is server-side only and the tool schema is
unchanged."
```

---

### Task 4: Child names as people type them

**Files:**
- Modify: `backend/assistant/tools.py` (`_resolve_summary`, new `_name_words`)
- Test: `backend/assistant/tests/test_tool_resolvers.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `tools._name_words(term: str) -> list[str]`. The `summary` result
  shape is unchanged — it feeds the `match: one | several | none` states the
  panel already renders, so there is no frontend change.

- [ ] **Step 1: Write the failing tests**

Add to `backend/assistant/tests/test_tool_resolvers.py`:

```python
class ChildNameMatchingTest(ResolverTestBase):
    """`fullname__icontains` is one exact substring. Real users type a first
    name, a misremembered surname, or "si Ana"."""

    def test_a_first_name_alone_finds_the_child(self):
        out = self._resolve(self.psy, "get_child_summary", {"name": "Maria"})
        self.assertEqual(out["match"], "one")
        self.assertEqual(out["child"]["name"], "Maria Santos")

    def test_a_wrong_surname_still_finds_them_by_first_name(self):
        # Observed shape: the record says "Maria Santos", the user types a
        # surname from memory. One exact substring finds nothing at all.
        out = self._resolve(self.psy, "get_child_summary", {"name": "Maria Reyes"})
        self.assertEqual(out["match"], "one")
        self.assertEqual(out["child"]["name"], "Maria Santos")

    def test_a_short_name_is_not_discarded(self):
        # _search_words drops anything under 4 characters, which would throw
        # away "Ana", "Jun" and "Lito" entirely. Names need their own splitter.
        Child.objects.create(fullname="Ana Cruz", assigned_psychologist=self.psy)
        out = self._resolve(self.psy, "get_child_summary", {"name": "Ana"})
        self.assertEqual(out["match"], "one")

    def test_a_tagalog_article_is_ignored(self):
        out = self._resolve(self.psy, "get_child_summary", {"name": "si Maria"})
        self.assertEqual(out["match"], "one")

    def test_several_matches_still_disambiguate(self):
        Child.objects.create(fullname="Maria Lopez", assigned_psychologist=self.psy)
        out = self._resolve(self.psy, "get_child_summary", {"name": "Maria"})
        self.assertEqual(out["match"], "several")
        self.assertEqual(len(out["items"]), 2)

    def test_a_name_outside_scope_is_not_found(self):
        out = self._resolve(self.psy, "get_child_summary", {"name": "Juan"})
        self.assertEqual(out["match"], "none")

    def test_an_unknown_name_is_still_not_found(self):
        out = self._resolve(self.psy, "get_child_summary", {"name": "Zenaida"})
        self.assertEqual(out["match"], "none")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && .venv/Scripts/python.exe manage.py test assistant.tests.test_tool_resolvers.ChildNameMatchingTest -v 2`
Expected: FAIL — `test_a_wrong_surname_still_finds_them_by_first_name` and
`test_a_tagalog_article_is_ignored` return `match == "none"`.

- [ ] **Step 3: Add a name-specific splitter**

In `backend/assistant/tools.py`, add below `_search_words`:

```python
# Articles and honorifics that arrive attached to a name: "si Maria",
# "kay Ana po". They are not part of anybody's name.
_NAME_NOISE = {"si", "ni", "kay", "kina", "sina", "po", "ho", "ang", "yung",
               "iyong", "mr", "ms", "mrs", "sir", "maam", "ma"}


def _name_words(term):
    """Words from a name worth matching on.

    _search_words is not reusable here: it drops anything under four
    characters, which discards "Ana", "Jun" and "Lito" — exactly the names
    people are most likely to type on their own.
    """
    words = {w for w in re.findall(r"[\w']+", str(term or "").lower())
             if len(w) >= 2}
    return sorted(words - _NAME_NOISE)
```

- [ ] **Step 4: Widen the lookup, without loosening the precise case**

In `_resolve_summary`, replace the first line of the body:

```python
    matches = list(_scope(request).filter(fullname__icontains=args["name"])[:6])
```

with:

```python
    from django.db.models import Q

    # The exact phrase first, so a full name keeps matching exactly as before
    # and nothing gets looser. Only when that finds nothing does the search
    # widen to any single word — which is what rescues "Maria Reyes" for a
    # record reading "Maria Santos", and "si Maria" for "Maria".
    matches = list(_scope(request).filter(fullname__icontains=args["name"])[:6])
    if not matches:
        query = Q()
        for word in _name_words(args["name"]):
            query |= Q(fullname__icontains=word)
        if query:
            matches = list(_scope(request).filter(query)[:6])
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd backend && .venv/Scripts/python.exe manage.py test assistant.tests.test_tool_resolvers -v 2`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/assistant/tools.py backend/assistant/tests/test_tool_resolvers.py
git commit -m "Find a child when the name is half-remembered

One exact substring found nothing for 'Maria Reyes' when the record read
'Maria Santos', and nothing for 'si Maria' either. The exact phrase is
still tried first, so a full name matches exactly as precisely as before;
only when that finds nothing does the search widen to any single word,
feeding the same one/several/none states the panel already renders.

Names needed their own splitter — the concern search's drops anything
under four characters, which is most of Ana, Jun and Lito."
```

---

### Task 5: `list_self_report_flags`

**Files:**
- Modify: `backend/assistant/tools.py` (resolver + registry entry)
- Modify: `backend/assistant/prompts.py` (two examples)
- Test: `backend/assistant/tests/test_tool_resolvers.py`

**Interfaces:**
- Consumes: `tools.period_range` (Task 1).
- Produces: result dict
  `{"kind": "self_report_flags", "state": str, "items": [{"child_id": int,
  "child": str, "question": str, "answer": str, "date": str,
  "reviewed": bool}]}`. Task 6 renders it.

- [ ] **Step 1: Write the failing tests**

Add to `backend/assistant/tests/test_tool_resolvers.py`. Add
`OpinionnaireInvite, SelfReportFlag` to the `clinical.models` import at the top.

```python
class SelfReportFlagsResolverTest(ResolverTestBase):
    """The child's own words. Exempt from the carry-history control — a
    child's words are not a colleague's prior opinions — so no author
    filtering applies, but scope still does."""

    def _flag(self, child, answer="Lagi akong umiiyak sa gabi", reviewed=False):
        invite = OpinionnaireInvite.objects.create(child=child)
        flag = SelfReportFlag.objects.create(
            invite=invite, child=child,
            question="How have you been feeling?", answer=answer,
            source=SelfReportFlag.LEXICON, matched="umiiyak")
        if reviewed:
            flag.reviewed_by = self.psy
            flag.reviewed_at = timezone.now()
            flag.save(update_fields=["reviewed_by", "reviewed_at"])
        return flag

    def test_it_returns_the_childs_own_words(self):
        self._flag(self.mine)
        out = self._resolve(self.psy, "list_self_report_flags", {})
        self.assertEqual(out["kind"], "self_report_flags")
        self.assertEqual(len(out["items"]), 1)
        self.assertEqual(out["items"][0]["child"], "Maria Santos")
        self.assertEqual(out["items"][0]["answer"], "Lagi akong umiiyak sa gabi")

    def test_another_psychologists_child_is_not_visible(self):
        self._flag(self.theirs)
        out = self._resolve(self.psy, "list_self_report_flags", {})
        self.assertEqual(out["items"], [])

    def test_unreviewed_is_the_default(self):
        self._flag(self.mine, reviewed=True)
        out = self._resolve(self.psy, "list_self_report_flags", {})
        self.assertEqual(out["items"], [])

    def test_state_all_includes_reviewed_flags(self):
        self._flag(self.mine, reviewed=True)
        out = self._resolve(self.psy, "list_self_report_flags", {"state": "all"})
        self.assertEqual(len(out["items"]), 1)
        self.assertTrue(out["items"][0]["reviewed"])

    def test_a_period_narrows_the_list(self):
        self._flag(self.mine)
        today = self._resolve(self.psy, "list_self_report_flags",
                              {"period": "today"})
        self.assertEqual(len(today["items"]), 1)
        last_year = self._resolve(self.psy, "list_self_report_flags",
                                  {"period": "last_year"})
        self.assertEqual(last_year["items"], [])

    def test_an_administrator_sees_every_child(self):
        self._flag(self.mine)
        self._flag(self.theirs)
        out = self._resolve(self.admin, "list_self_report_flags", {})
        self.assertEqual(len(out["items"]), 2)


class SelfReportFlagsSchemaTest(SimpleTestCase):
    def test_both_arguments_are_optional(self):
        call = tools.validate("list_self_report_flags", {})
        self.assertTrue(call.ok, call.error)

    def test_an_invented_argument_is_discarded(self):
        call = tools.validate("list_self_report_flags",
                              {"child": "Maria", "state": "all"})
        self.assertTrue(call.ok, call.error)
        self.assertEqual(call.args, {"state": "all"})
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && .venv/Scripts/python.exe manage.py test assistant.tests.test_tool_resolvers -v 2`
Expected: FAIL — `KeyError: 'list_self_report_flags'` from `REGISTRY`.

- [ ] **Step 3: Write the resolver**

Add to `backend/assistant/tools.py`, above `REGISTRY`:

```python
def _resolve_self_report_flags(request, args):
    """Children who said something worth reading, in their own words.

    Self-reports are exempt from the carry-history control: a child's own
    words are not a previous psychologist's opinions, so no author filter
    applies here. Scope still does, through the same helper as every other
    tool.

    The answer text is included because the child report screen already shows
    these expanded above the case notes, and a flag without the words is not
    something anyone can act on.
    """
    from clinical.models import SelfReportFlag

    state = args.get("state", "unreviewed")
    qs = (SelfReportFlag.objects
          .filter(child__in=_scope(request))
          .select_related("child"))
    if state != "all":
        qs = qs.filter(reviewed_at__isnull=True)

    period = args.get("period")
    if period:
        start, end = period_range(period)
        qs = qs.filter(created_at__date__gte=start, created_at__date__lt=end)

    return {"kind": "self_report_flags", "state": state, "items": [
        {"child_id": f.child_id, "child": f.child.fullname,
         "question": f.question, "answer": f.answer,
         "date": str(timezone.localtime(f.created_at).date()),
         "reviewed": f.reviewed_at is not None}
        for f in qs[:20]]}
```

Add `from django.utils import timezone` at the top of the module if it is not
already imported at module level (it is currently imported inside functions —
add a module-level import and leave the local ones alone).

- [ ] **Step 4: Register the tool**

Add to `REGISTRY`, immediately before the `answer_directly` entry:

```python
    "list_self_report_flags": {
        "description": (
            "Children who wrote something worth reading in their own "
            "self-report — distress, fear, sadness, being alone. Use for "
            "'who flagged something', 'anyone worrying', 'self-report "
            "concerns'. Do NOT use for case notes written by staff."),
        "schema": {
            "state": {"enum": ["unreviewed", "all"], "required": False},
            "period": {"enum": list(PERIODS), "required": False},
        },
        "echo": lambda a: "Looking up: flagged self-reports",
        "resolve": _resolve_self_report_flags,
    },
```

- [ ] **Step 5: Add two prompt examples**

In `backend/assistant/prompts.py`, add to the examples block inside
`CHAT_SYSTEM`, immediately before the `"Good morning!"` line:

```
  "Who flagged something worrying?"   -> list_self_report_flags()
  "Sino ang may nakakabahala?"        -> list_self_report_flags()
  "Who did I see kahapon?"            -> list_my_appointments(when="yesterday")
```

This edits the static prefix once. It must stay identical thereafter.

- [ ] **Step 6: Run the tests to verify they pass**

Run: `cd backend && .venv/Scripts/python.exe manage.py test assistant.tests.test_tool_resolvers assistant.tests.test_prompts -v 2`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add backend/assistant/tools.py backend/assistant/prompts.py backend/assistant/tests/test_tool_resolvers.py
git commit -m "Let someone ask which children flagged something themselves

Self-report flags were built to surface a child's own words about
distress and had no conversational surface at all — the highest-stakes
data in the system, reachable only by opening the right screen.

Both arguments are optional, because a required argument the model drops
once in 28 turns is a failed turn. The words themselves are included:
the child report screen already shows them expanded, and a flag without
them is not something anyone can act on."
```

---

### Task 6: Render the new results

**Files:**
- Modify: `frontend/src/components/AssistantPanel.jsx` (new `kind` branch,
  status label on appointments)

**Interfaces:**
- Consumes: the `self_report_flags` dict (Task 5) and the `status` key on
  appointment items (Task 2).
- Produces: nothing later tasks depend on.

- [ ] **Step 1: Fix the empty-state wording for past periods**

The branch currently returns `<Line muted>Nothing scheduled.</Line>`, which is
wrong for "who did I see yesterday?" — nothing was *scheduled* is not the same
statement as nothing *happened*. Key it off the period, which the result
already carries as `result.when`:

```jsx
    if (!result.items.length) {
      const past = ['yesterday', 'last_week', 'last_month', 'last_year']
        .includes(result.when);
      return <Line muted>{past ? 'Nothing recorded.' : 'Nothing scheduled.'}</Line>;
    }
```

- [ ] **Step 2: Add the status label to appointments**

In `AssistantPanel.jsx`, inside the `kind === 'appointments'` branch (around
line 77), render `item.status` beside the time. Show it only when it is not
`scheduled`, so today's ordinary list stays uncluttered:

```jsx
{a.status && a.status !== 'scheduled' && (
  <span style={{
    marginLeft: 6, padding: '1px 6px', borderRadius: 'var(--radius-pill)',
    fontSize: 11, fontWeight: 700, textTransform: 'capitalize',
    background: 'var(--ink-50)', color: 'var(--text-muted)',
  }}>{a.status.replace('_', ' ')}</span>
)}
```

- [ ] **Step 3: Add the `self_report_flags` renderer**

Add a branch beside the existing ones, before the `kind === 'message'` line:

```jsx
  if (kind === 'self_report_flags') {
    if (!result.items.length) {
      return <Line muted>No flagged self-reports.</Line>;
    }
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {result.items.map((f, i) => (
          <div key={i} style={{
            padding: '10px 12px', borderRadius: 'var(--radius-md)',
            background: 'var(--amber-50)',
            border: '1px solid var(--border)',
          }}>
            <div style={{ fontWeight: 700, fontSize: 13 }}>
              {f.child}
              {f.reviewed && (
                <span style={{ marginLeft: 6, fontSize: 11, fontWeight: 600, color: 'var(--text-muted)' }}>
                  reviewed
                </span>
              )}
            </div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>
              {f.question}
            </div>
            <div style={{ fontSize: 13, marginTop: 4, fontStyle: 'italic' }}>
              “{f.answer}”
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-faint)', marginTop: 4 }}>
              {f.date}
            </div>
          </div>
        ))}
      </div>
    );
  }
```

- [ ] **Step 4: Verify it builds and lints**

Run: `cd frontend && npm run lint && npm run build`
Expected: both exit 0, no errors.

- [ ] **Step 5: Verify it renders in the browser**

`npm run build` exits 0 on a page that renders nothing, so this must be seen.
Start the app with `run-local.bat`, sign in as `admin@racco1.gov.ph` /
`admin1234`, open the assistant panel and ask "who flagged something
worrying?". Confirm the cards render and the text is readable. If the local
database has no flags, run `cd backend && .venv/Scripts/python.exe manage.py
scan_self_reports` first — it is idempotent.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/AssistantPanel.jsx
git commit -m "Show flagged self-reports and how an appointment ended

A past period now answers with sessions that already happened, so the
list has to say which ones were completed or missed — the status shows
only when it is not 'scheduled', so an ordinary day stays uncluttered."
```

---

### Task 7: A quick-action door, and what greets you through it

**Files:**
- Modify: `backend/assistant/views.py` (new `AssistantCapabilitiesView`)
- Modify: `backend/assistant/urls.py` (route it)
- Test: `backend/assistant/tests/test_ask.py`
- Modify: `frontend/src/api/assistant.js` (fetch it)
- Create: `frontend/src/context/AssistantContext.jsx`
- Modify: `frontend/src/App.jsx` (wrap with the provider)
- Modify: `frontend/src/components/AssistantPanel.jsx` (read `open` from
  context; show examples when empty)
- Modify: `frontend/src/pages/Dashboard.jsx` (the quick action)

**Interfaces:**
- Consumes: `tools.capability_text`, `tools.capability_examples` (Task 3).
- Produces: `useAssistant()` returning `{ open, openAssistant, closeAssistant }`,
  and `GET /api/assistant/capabilities/` returning
  `{"can_ask": str, "examples": [str]}`.

- [ ] **Step 1: Write the failing endpoint test**

Add to `backend/assistant/tests/test_ask.py`:

```python
class CapabilitiesEndpointTest(APITestCase):
    """The empty panel and the refusal text must not disagree about what this
    user can ask, so both read the same server-side source."""

    def setUp(self):
        from accounts.models import Role
        from django.contrib.auth import get_user_model
        User = get_user_model()
        psy_role = Role.objects.create(role_name=Role.PSYCHOLOGIST)
        self.psy = User.objects.create_user(
            email="p@racco1.gov.ph", username="p", password="pass1234",
            role=psy_role)

    def test_it_names_what_this_role_can_ask(self):
        self.client.force_authenticate(self.psy)
        resp = self.client.get("/api/assistant/capabilities/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("caseload", resp.data["can_ask"].lower())
        self.assertTrue(resp.data["examples"])

    def test_it_requires_authentication(self):
        resp = self.client.get("/api/assistant/capabilities/")
        self.assertIn(resp.status_code, (401, 403))
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd backend && .venv/Scripts/python.exe manage.py test assistant.tests.test_ask -v 2`
Expected: FAIL — 404, the route does not exist.

- [ ] **Step 3: Add the view and route**

In `backend/assistant/views.py`, beside the other views:

```python
class AssistantCapabilitiesView(AssistantBaseView):
    """What this user can ask. Read by the panel's empty state so a person who
    opened it from a button has somewhere to start.

    Deliberately not gated on the assistant being switched on: the answer is a
    fixed sentence, needs no model, and an empty panel with no hint is worse
    than one that explains itself.
    """

    def get(self, request):
        role = _role(request)
        return Response({"can_ask": tools.capability_text(role),
                         "examples": tools.capability_examples(role)})
```

In `backend/assistant/urls.py`, add beside the `ask/` route:

```python
    path("capabilities/", views.AssistantCapabilitiesView.as_view(),
         name="assistant-capabilities"),
```

- [ ] **Step 4: Run it to verify it passes**

Run: `cd backend && .venv/Scripts/python.exe manage.py test assistant.tests.test_ask -v 2`
Expected: PASS

- [ ] **Step 5: Add the client call**

In `frontend/src/api/assistant.js`:

```js
export const getAssistantCapabilities = () =>
  api.get('/assistant/capabilities/').then((r) => r.data);
```

- [ ] **Step 6: Create the context**

`frontend/src/context/AssistantContext.jsx`:

```jsx
import React, { createContext, useContext, useMemo, useState } from 'react';

/* The panel's open state used to live inside AssistantPanel, which meant
 * nothing outside it could open the assistant. It is lifted here so a quick
 * action can, matching how Auth, Toast and Activity are already shared. */
const AssistantCtx = createContext({
  open: false, openAssistant: () => {}, closeAssistant: () => {},
});

export function AssistantProvider({ children }) {
  const [open, setOpen] = useState(false);
  const value = useMemo(() => ({
    open,
    openAssistant: () => setOpen(true),
    closeAssistant: () => setOpen(false),
  }), [open]);
  return <AssistantCtx.Provider value={value}>{children}</AssistantCtx.Provider>;
}

export const useAssistant = () => useContext(AssistantCtx);
```

- [ ] **Step 7: Wrap the app in the provider**

In `frontend/src/App.jsx`, import `AssistantProvider` and open it immediately
inside `<ActivityProvider>` (line 46), closing immediately before
`</ActivityProvider>` (line 72). Both the panel (rendered at line 37, inside
the shell) and the Dashboard sit below that point, so they share one instance:

```jsx
      <ActivityProvider>
      <AssistantProvider>
        {/* ...existing children unchanged... */}
      </AssistantProvider>
      </ActivityProvider>
```

- [ ] **Step 8: Read the state from context in the panel**

In `AssistantPanel.jsx`, replace the local `const [open, setOpen] = useState(false)`
with:

```jsx
  const { open, openAssistant, closeAssistant } = useAssistant();
```

Replace `setOpen(true)` with `openAssistant()` and `setOpen(false)` with
`closeAssistant()` throughout the file. **Check every call site** — the close
button near line 291 and the floating button near line 205 both use it.

- [ ] **Step 9: Show example questions in the empty panel**

`AssistantPanel.jsx` already computes `const empty = turns.length === 0;`. Fetch
the capabilities once when the panel first opens and render the examples as
clickable chips that submit themselves — a person who arrived by clicking a
button has typed nothing.

```jsx
  const [caps, setCaps] = useState(null);
  useEffect(() => {
    if (open && !caps) getAssistantCapabilities().then(setCaps).catch(() => {});
  }, [open, caps]);
```

Then inside the `empty` branch of the panel body:

```jsx
  {caps && (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <div style={{ fontSize: 12.5, color: 'var(--text-muted)', lineHeight: 1.5 }}>
        {caps.can_ask}
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
        {caps.examples.map((q) => (
          <button key={q} type="button" onClick={() => submit(q)} style={{
            padding: '6px 10px', borderRadius: 'var(--radius-pill)',
            border: '1px solid var(--border)', background: 'var(--surface)',
            color: 'var(--text-body)', fontSize: 12, cursor: 'pointer',
            fontFamily: 'var(--font-sans)',
          }}>{q}</button>
        ))}
      </div>
    </div>
  )}
```

`submit` is the panel's existing send handler. If it currently reads the input
state rather than taking an argument, give it an optional parameter
(`const submit = (preset) => { const asked = preset ?? question; ... }`) rather
than duplicating the send logic — there must be one path to the endpoint.

Import `getAssistantCapabilities` from `../api/assistant` and `useEffect` from
React if they are not already imported.

- [ ] **Step 10: Add the quick action**

In `frontend/src/pages/Dashboard.jsx`, import `useAssistant`, call it in the
component, then add to the `actions` array (after `Records`):

```jsx
    // Not a second chatbot — the same panel, reachable without hunting for
    // the floating button. `sparkles` is already this row's own header icon,
    // so repeating it would read as decoration.
    { label: 'Ask AI', icon: 'bot', variant: 'secondary', onClick: openAssistant, roles: ['Administrator', 'Psychologist', 'Staff'] },
```

Then teach the renderer to honour `onClick` alongside `to`:

```jsx
        {actions.map((a) => (
          <Button key={a.label} variant={a.variant}
                  onClick={a.onClick ? a.onClick : () => navigate(a.to)}
                  iconLeft={<Icon name={a.icon} size={16} />}>{a.label}</Button>
        ))}
```

- [ ] **Step 11: Verify it builds and lints**

Run: `cd frontend && npm run lint && npm run build`
Expected: both exit 0. Lint matters most here — `react-hooks/rules-of-hooks`
catches a `useAssistant()` or `useEffect()` call placed below an early return,
which has already happened once in this codebase and crashed a page for every
user until someone opened it.

- [ ] **Step 12: Verify it works in the browser**

Start with `run-local.bat`, sign in, and from the Dashboard click **Ask AI**.
Confirm the panel opens, shows the capability sentence and the example chips,
and that clicking a chip sends that question. Confirm the floating button still
opens it and the close button still closes it. Check all three roles: the
button appears for each, and the examples differ between a psychologist and an
administrator.

- [ ] **Step 13: Commit**

```bash
git add backend/assistant/views.py backend/assistant/urls.py backend/assistant/tests/test_ask.py frontend/src/api/assistant.js frontend/src/context/AssistantContext.jsx frontend/src/App.jsx frontend/src/components/AssistantPanel.jsx frontend/src/pages/Dashboard.jsx
git commit -m "Put a door to the assistant where people are already looking

The panel's open state lived inside the panel, so nothing else could
open it — the quick actions row could only navigate. Lifted into a
context alongside Auth, Toast and Activity.

One more door to the same assistant, not a second one: same endpoint,
same panel, same stateless session. Arriving through it shows what this
role can ask, served from the same source as the refusal text so the two
can never drift apart."
```

---

### Task 8: Measure the routing, including the arguments

`ai_eval` scores which tool was chosen and never which arguments were filled in,
so the `kahapon` fix is invisible to it — the case would pass while still
answering with today's appointments.

**Files:**
- Modify: `backend/assistant/management/commands/ai_eval.py` (`CHAT_CASES`
  gains a fifth element; the scoring loop checks it)

**Interfaces:**
- Consumes: every tool from Tasks 1-5.
- Produces: nothing later tasks depend on.

- [ ] **Step 1: Widen the case tuple**

Every entry in `CHAT_CASES` becomes a 5-tuple
`(label, question, expected_tool, expect_hits, expected_args)`, where
`expected_args` is a dict checked as a subset of the validated call's args, or
`None` to check nothing. Add `None` to each of the fourteen existing entries,
then add:

```python
    # Regression: kahapon was aliased to today, so this answered with today's
    # appointments. Routing alone cannot catch it — the argument has to be
    # checked.
    ("past tl", "Sino ang nakita ko kahapon?", "list_my_appointments", False,
     {"when": "yesterday"}),
    ("past en", "Who did I see yesterday?", "list_my_appointments", False,
     {"when": "yesterday"}),
    ("last week en", "What did I do last week?", "list_my_appointments", False,
     {"when": "last_week"}),
    ("month tl", "Ilan ang appointments ko ngayong buwan?",
     "list_my_appointments", False, {"when": "this_month"}),
    ("year en", "What have I got this year?", "list_my_appointments", False,
     {"when": "this_year"}),
    ("flags en", "Who flagged something worrying?",
     "list_self_report_flags", False, None),
    ("flags tl", "Sino ang may nakakabahala sa sinulat nila?",
     "list_self_report_flags", False, None),
    ("greeting tl", "Salamat po!", "answer_directly", False,
     {"reason": "greeting_or_closing"}),
    ("name partial", "Tell me about Maria", "get_child_summary", False, None),
    ("action en", "Book Ana for Friday", "answer_directly", False, None),
```

- [ ] **Step 2: Check the arguments in the scoring loop**

In `_chat`, change the loop header to unpack five values:

```python
        for label, question, expected, expect_hits, expected_args in CHAT_CASES:
```

and add, immediately after the existing `if not call.ok:` / `elif expect_hits:`
block:

```python
                if call.ok and expected_args:
                    wrong = {k: call.args.get(k) for k, v in expected_args.items()
                             if call.args.get(k) != v}
                    if wrong:
                        found["wrong argument"] = [f"{wrong} != {expected_args}"]
```

- [ ] **Step 3: Run the evaluation**

Requires a live Ollama — it is not part of the test suite.

Run: `cd backend && .venv/Scripts/python.exe manage.py ai_eval --feature chat --reps 3`
Expected: routing accuracy **at or above the 55/55 baseline**, no
"wrong argument" flags, and no "empty answer" flags on cases where
`expect_hits` is true.

**If the gate fails**, the period vocabulary shrinks rather than ships: drop
the month and year values from `PERIODS`, keep the day and week ones (which
include the `kahapon` fix), and re-run. Record what was dropped and why.

- [ ] **Step 4: Commit**

```bash
git add backend/assistant/management/commands/ai_eval.py
git commit -m "Score the arguments, not just which tool was picked

The evaluation checked the tool name and stopped. kahapon routed to
list_my_appointments correctly and then asked for the wrong day, which
scored as a pass — the defect this whole change exists to fix was
invisible to the thing measuring it.

Cases now carry the arguments they expect, and the period vocabulary is
covered in both registers."
```

---

### Task 9: Full verification gate

Nothing here is optional, and per-task runs do not substitute for it. Both
commands, every time, before anything is pushed.

- [ ] **Step 1: Run the whole backend suite**

Run: `cd backend && .venv/Scripts/python.exe manage.py test`
Expected: OK. The count should be roughly 728 + the tests added here.

- [ ] **Step 2: Run the frontend gate**

Run: `cd frontend && npm run lint && npm run build`
Expected: both exit 0. `npm run build` alone is not enough — Vite reports
syntax errors only, and a hook below an early return builds perfectly and then
throws at runtime.

- [ ] **Step 3: Load every screen the change touches**

A page that renders nothing still exits `npm run build` with code 0. With
`run-local.bat` running, open the Dashboard (quick action), and the assistant
panel from both doors, on each of the three roles.

- [ ] **Step 4: Push**

```bash
git push
```

`git push` goes to `local-ver` and auto-deploys the demo. Do **not**
`git push origin` — that deploys the live system and needs asking first, in so
many words.
