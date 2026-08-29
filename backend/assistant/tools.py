"""The chatbot's tool registry and its validator.

The model's entire job is to pick one of these and fill in its arguments. It
never sees what comes back — results go from the database to a UI component,
so a turn costs about five seconds and case data is never in a position to be
invented.

Everything the validator does exists because the spike observed the failure:

* the model emitted a key with a colon in it, `{"when: ": "today"}`
* it returned `{"when": "bukas"}` where the enum allowed only English values
* it dropped every optional free-text argument on every call

So arguments are treated as untrusted input, and scope is never read from them:
no tool declares a "which children" parameter, because the answer always comes
from `request.user`.
"""
from dataclasses import dataclass, field
from datetime import date, timedelta
import re

# Enum values the model reached for that were not in the enum. Deterministic,
# instant, free — and the single change that took measured accuracy from 91%
# to 100% on the spike's case set.
ALIASES = {
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
    "status": {
        "aktibo": "active", "buhay": "active", "tapos": "terminated",
        "lahat": "any", "all": "any",
    },
}

# The table is keyed by PARAMETER NAME, and two tools name their time argument
# differently — appointments call it `when`, flags call it `period`. Without
# this, "ngayong taon" would resolve on one and be rejected on the other for no
# reason a user could see.
ALIASES["period"] = ALIASES["when"]

_PUNCT = re.compile(r"[^\w]+")


@dataclass
class ToolCall:
    """The result of validating what the model produced."""
    tool: str
    args: dict = field(default_factory=dict)
    ok: bool = True
    error: str = ""
    echo: str = ""


def _clean_key(key):
    """`"when: "` and `"  status  "` both become the parameter's real name."""
    return _PUNCT.sub("", str(key)).strip().lower()


def _coerce(param, value, meta):
    """Return (value, error). Enums are matched case-insensitively, then via
    the alias table, and only then rejected."""
    if not isinstance(value, str):
        value = "" if value is None else str(value)
    value = value.strip()

    if "enum" not in meta:
        return (value, "") if value else (
            "", f"'{param}' cannot be empty.")

    low = value.lower()
    if low in meta["enum"]:
        return low, ""
    aliased = ALIASES.get(param, {}).get(low)
    if aliased in meta["enum"]:
        return aliased, ""
    return "", (f"'{param}' must be one of {', '.join(meta['enum'])} "
                f"— got '{value}'.")


def validate(tool, raw_args):
    """Turn the model's output into a ToolCall, or explain why it cannot be."""
    spec = REGISTRY.get(tool)
    if spec is None:
        return ToolCall(tool=tool, ok=False,
                        error=f"'{tool}' is not something I can do.")

    schema = spec["schema"]
    supplied = {_clean_key(k): v for k, v in (raw_args or {}).items()}
    args, errors = {}, []

    for param, meta in schema.items():
        if param not in supplied:
            if meta.get("required"):
                errors.append(f"'{param}' is required.")
            continue
        value, err = _coerce(param, supplied[param], meta)
        if err:
            errors.append(err)
        else:
            args[param] = value

    # Anything the schema does not declare is discarded, never passed through.
    # An invented "assigned_to_me" must not reach a queryset.
    if errors:
        return ToolCall(tool=tool, ok=False, error=" ".join(errors))
    return ToolCall(tool=tool, args=args, echo=spec["echo"](args))



# --- misroute guard --------------------------------------------------------
# Observed in the browser: "how many psychologist are in the system?" answered
# "40 active children". The cause was count_my_children's own description,
# which said "Use for questions starting 'how many'". Rewording it fixed two
# phrasings out of four — not good enough for a tool that answers with a
# confident number, and a confidently wrong answer is the worst failure this
# chatbot has. So the wording change is backed by a deterministic check.

_PEOPLE_WHO_WORK_HERE = (
    "psychologist", "psychologists", "psych", "psikologo", "psychologo",
    "staff", "employee", "employees", "worker", "workers", "kawani",
    "tauhan", "empleyado", "user", "users", "account", "accounts",
    "administrator", "administrators", "admin", "admins", "doctor", "doctors",
    "social worker", "social workers",
)

_ABOUT_CHILDREN = (
    "child", "children", "kid", "kids", "bata", "batang", "case", "cases",
    "caseload", "ward", "wards", "client", "clients",
)


def correct_obvious_misroute(question, call):
    """Stop a child count being served as the answer to a staff question.

    Only downgrades to `answer_directly`, never upgrades or re-routes: the
    guard can make the assistant decline, and cannot make it assert anything.
    A question naming both — "how many children were referred by staff?" — is
    left alone, because children are the subject and the tool can answer it.
    """
    if not call.ok or call.tool != "count_my_children":
        return call
    low = _PUNCT.sub(" ", str(question or "").lower())
    words = f" {low} "
    names_people = any(f" {w} " in words for w in _PEOPLE_WHO_WORK_HERE)
    names_children = any(f" {w} " in words for w in _ABOUT_CHILDREN)
    if names_people and not names_children:
        return ToolCall(tool="answer_directly", args={"reason": "unsupported"},
                        echo="", )
    return call


# Imperatives, not topics. "schedule" is absent on purpose — it appears in
# "what is my schedule today?", which is a question this assistant answers.
_ACTION_VERBS = (
    "book", "cancel", "create", "add", "delete", "remove", "reset", "update",
    "edit", "assign", "reassign", "upload", "send", "approve", "deactivate",
    "magdagdag", "magbook", "burahin", "palitan", "tanggalin", "idagdag",
)


def correct_action_request(question, call):
    """Answer "book Ana for Friday" with "I can't change anything".

    Measured: the model routes that to list_my_appointments 3 times out of 3,
    so a request to CREATE a booking was answered with a LIST of bookings.
    Guarding only answer_directly never fired, because the model had already
    picked a data tool.

    So this downgrades whatever was chosen, exactly as
    correct_obvious_misroute does for a staff question. The safety property is
    unchanged and is the reason both are allowed to exist: they can only make
    the assistant decline, never make it assert anything.

    `action_request` is server-side only: this constructs its ToolCall
    directly, so validate() never sees the value and the schema the model
    reads does not grow by it.
    """
    if not call.ok:
        return call
    words = _PUNCT.sub(" ", str(question or "").lower()).split()
    if not words:
        return call
    # Tagalog forms an imperative by prefixing the verb: "i-reset mo ang
    # password". _PUNCT has already turned that hyphen into a space, so the
    # verb is the second word and "i" is the first — checking the pair covers
    # every i- verb without listing them.
    leading = words[0]
    if leading == "i" and len(words) > 1:
        leading = words[1]
    if leading in _ACTION_VERBS:
        return ToolCall(tool="answer_directly",
                        args={"reason": "action_request"}, echo="")
    return call


# Openings and sign-offs, English and Tagalog.
_GREETING_WORDS = (
    "hello", "hi", "hey", "good", "morning", "afternoon", "evening",
    "thanks", "thank", "cheers", "bye", "goodbye",
    "salamat", "magandang", "kumusta", "kamusta", "paalam", "sige",
)


def correct_greeting(question, call):
    """Recover greeting_or_closing when the model left `reason` out.

    Measured: on "Good morning!" the model omits `reason` 2 times in 3. The
    argument is optional on purpose — requiring it turned a correct routing
    decision into a failed turn — so the reason has to be recoverable without
    the model, or the greeting reply is dead code most of the time and
    "salamat po" still gets a list of features.

    Short questions only: "Good morning, how many children do I have?" is a
    question with a greeting attached, not a greeting.
    """
    if not call.ok or call.tool != "answer_directly":
        return call
    if call.args.get("reason") == "action_request":
        return call                       # already classified, and not a greeting
    words = _PUNCT.sub(" ", str(question or "").lower()).split()
    if words and len(words) <= 4 and words[0] in _GREETING_WORDS:
        return ToolCall(tool="answer_directly",
                        args={"reason": "greeting_or_closing"}, echo="")
    return call


# --- resolvers ------------------------------------------------------------
# Each takes (request, validated args) and returns a plain dict the frontend
# renders. The model never sees any of this — which is precisely why a
# hallucinated child name is impossible here: names come out of the database.
#
# Scope is taken from request.user through the same helper the rest of the app
# uses. No resolver reads scope from the model's arguments.

# Periods. Weeks, months and years are calendar-aligned; days are offsets.
# Rolling windows ("today through +7") do not survive `last_month`, and mixing
# the two would have "this week" and "this month" answering on different logic.
PERIODS = ("today", "yesterday", "tomorrow",
           "this_week", "last_week", "next_week",
           "this_month", "last_month",
           "this_year", "last_year")

# Appointments stop at the month. Measured: offering the year sent "what have
# I got this year?" to list_care_gaps 3 times out of 3, and no psychologist
# asks to see a year of appointments anyway — the value bought nothing and
# cost a misroute. Review questions about flags do reach a year, so the full
# vocabulary stays available there.
APPOINTMENT_PERIODS = tuple(p for p in PERIODS if not p.endswith("_year"))

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


def _scope(request):
    from assistant.views import _visible_children      # local: avoids a cycle
    return _visible_children(request)


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


def _resolve_count(request, args):
    from children.models import Child
    qs = _scope(request)
    if args["status"] == "active":
        qs = qs.filter(status=Child.ACTIVE)
    elif args["status"] == "terminated":
        qs = qs.exclude(status=Child.ACTIVE)
    return {"kind": "count", "status": args["status"], "count": qs.count()}


def _singular(word):
    """"emotions" -> "emotion", "difficulties" -> "difficulty".

    icontains only looks one way: a record reading "expressing emotion" does
    not contain "emotions", so the plural the user typed has to be reduced
    before it is matched. Observed live on exactly that question.
    """
    if word.endswith("ies") and len(word) > 4:
        return word[:-3] + "y"
    if word.endswith("s") and not word.endswith("ss") and len(word) > 4:
        return word[:-1]
    return word


def _stem_ing(word):
    """"sleeping" -> "sleep".

    icontains only matches a shorter needle in a longer record, so the record
    "Sleep disturbance" does not contain "sleeping". Measured: "Who has trouble
    sleeping?" returned nothing 3 times out of 3 for exactly that reason, which
    is the confident-empty answer this search already exists to prevent.
    """
    if word.endswith("ing") and len(word) > 5:
        return word[:-3]
    return word


def _search_words(term):
    """Words worth matching on, singular and un-inflected forms included.

    Short words are dropped: "of" and "the" appear inside so many records that
    matching them would return the whole caseload as a false hit.
    """
    words = {w for w in re.findall(r"[\w']+", term.lower()) if len(w) >= 4}
    return sorted(words | {_singular(w) for w in words}
                  | {_stem_ing(w) for w in words})


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


def _resolve_concern(request, args):
    """Match on shared words, not on the whole phrase.

    Measured against live data: the model says "school refusal"; this agency
    records "School attendance difficulty". An exact substring search connects
    those never — it returned zero for the English term as readily as for the
    Tagalog one, and a confident empty answer is the worst kind.

    Matching any significant word bridges the two vocabularies. When nothing
    matches at all, the recorded concerns are returned instead, so a dead end
    becomes something the user can act on — which is also what catches a
    Tagalog phrase the model did not translate.
    """
    from django.db.models import Q
    from clinical.models import ProblemEntry

    term = args["concern"]
    open_problems = (ProblemEntry.objects
                     .filter(child__in=_scope(request), resolved=False)
                     .select_related("child"))

    hits = []
    query = Q()
    for word in _search_words(term):
        query |= Q(description__icontains=word) | Q(category__icontains=word)
    if query:
        hits = list(open_problems.filter(query))

    # Names, never the problem text: ProblemEntry is one of the two models the
    # carry-history block does not filter, and returning descriptions would
    # walk straight into that gap.
    seen, items = set(), []
    for p in hits:
        if p.child_id not in seen:
            seen.add(p.child_id)
            items.append({"id": p.child_id, "name": p.child.fullname})

    out = {"kind": "children", "concern": term, "items": items}
    if not items:
        out["available"] = sorted(
            {p.description for p in open_problems if p.description})[:12]
    return out


def _resolve_summary(request, args):
    from assistant.views import _brief_only_author, _role
    from clinical.care_gaps import compute_alerts
    from children.models import Child

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
    if not matches:
        return {"kind": "summary", "match": "none", "name": args["name"]}
    if len(matches) > 1:
        return {"kind": "summary", "match": "several", "name": args["name"],
                "items": [{"id": c.id, "name": c.fullname} for c in matches]}

    child = matches[0]
    remarks = child.remarks.select_related("author")
    only = _brief_only_author(child, request.user, _role(request))
    if only is not None:
        remarks = remarks.filter(author=only)
    gaps = compute_alerts(Child.objects.filter(pk=child.pk))
    return {"kind": "summary", "match": "one", "child": {
        "id": child.id, "name": child.fullname, "status": child.status,
        "psychologist": getattr(child.assigned_psychologist, "fullname", None)},
        "remarks": [{"date": str(r.date), "text": r.text} for r in remarks[:5]],
        "gaps": [a.get("type") for a in gaps]}


def _resolve_care_gaps(request, args):
    """Reuses the same alerts the Monitoring screen shows, so the chatbot can
    never disagree with the table the user is looking at.

    `message` is carried through rather than `type`: the type is a slug
    ("consent_missing") that means nothing to a psychologist, while the message
    is the sentence the screen already shows them.
    """
    from clinical.care_gaps import compute_alerts
    alerts = compute_alerts(_scope(request))
    return {"kind": "care_gaps", "items": [
        {"child": a.get("child_name") or a.get("child"),
         "type": a.get("type"), "message": a.get("message"),
         "severity": a.get("severity")}
        for a in alerts]}


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
    from django.utils import timezone
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


def _resolve_direct(request, args):
    from assistant.views import _role          # local: avoids a cycle

    reason = args.get("reason", "unsupported")
    if reason == "greeting_or_closing":
        text = GREETING_REPLY
    elif reason == "action_request":
        text = ACTION_REPLY
    else:
        text = capability_text(_role(request))
    return {"kind": "message", "reason": reason, "text": text}


REGISTRY = {
    "list_my_appointments": {
        "description": (
            "The signed-in user's own schedule: appointments, sessions, visits, "
            "and WHO THEY ARE SEEING on a given day. Use for any question about "
            "the calendar or schedule. Do NOT use this to search for children."),
        "schema": {"when": {"enum": list(APPOINTMENT_PERIODS), "required": True}},
        "echo": lambda a: f"Looking up: your appointments {a['when'].replace('_', ' ')}",
        "resolve": _resolve_appointments,
    },
    "count_my_children": {
        "description": (
            "How many CHILDREN are in the user's caseload. Counts children "
            "only. Do NOT use to count psychologists, staff, users, "
            "appointments, reports, or anything else — this tool can only "
            "count children, and answering a question about staff with a "
            "child count is wrong. Do NOT use for schedule questions."),
        "schema": {"status": {"enum": ["active", "terminated", "any"],
                              "required": True}},
        "echo": lambda a: f"Looking up: how many {a['status']} children you have",
        "resolve": _resolve_count,
    },
    "search_children_by_concern": {
        "description": (
            # An example here becomes an argument: adding 'trouble sleeping'
            # made the model pass it verbatim, and "sleeping" does not match
            # the recorded "Sleep disturbance" — 3 empty answers out of 3. Any
            # example added here has to exist in the agency's own vocabulary.
            "Find children whose presenting concern or problem matches a "
            "description, for example 'school refusal', 'anxiety', "
            "'withdrawn', 'struggling with emotions'. "
            "This is the tool for ANY question about what children are "
            "struggling with, however it is worded. "
            "Always pass the concern the user named."),
        "schema": {"concern": {"required": True}},
        "echo": lambda a: f"Looking up: children with '{a['concern']}'",
        "resolve": _resolve_concern,
    },
    "get_child_summary": {
        "description": (
            "The case summary for ONE named child. Use whenever the user names "
            "a specific child and wants their history, rundown or summary."),
        "schema": {"name": {"required": True}},
        "echo": lambda a: f"Looking up: {a['name']}",
        "resolve": _resolve_summary,
    },
    "list_care_gaps": {
        "description": (
            "Children with overdue follow-ups, missing pre-assessments or "
            "missing reports. Use for 'who needs follow-up', 'who is overdue'."),
        "schema": {},
        "echo": lambda a: "Looking up: children needing follow-up",
        "resolve": _resolve_care_gaps,
    },
    "list_self_report_flags": {
        "description": (
            # Purely positive, and it names no clinical vocabulary at all.
            # A "Do NOT use for anxiety, emotions, sleep" clause was measured
            # WORSE: the router reads the keywords and drops the negation, so
            # listing what this tool is not for is how it got picked for
            # "struggling with emotions" 3 times in 3.
            "Children flagged from a survey THE CHILD FILLED IN THEMSELVES. "
            "Use only when the question asks what has been 'flagged', or what "
            "children have said or written about themselves in their own "
            "words."),
        "schema": {
            "state": {"enum": ["unreviewed", "all"], "required": False},
            "period": {"enum": list(PERIODS), "required": False},
        },
        "echo": lambda a: "Looking up: flagged self-reports",
        "resolve": _resolve_self_report_flags,
    },
    "answer_directly": {
        "description": (
            "Use when NO other tool fits: greetings, thanks, sign-offs, general "
            "knowledge, questions about what words mean, or anything not about "
            "this user's schedule, children or caseload. This includes "
            "questions about PEOPLE WHO WORK HERE — how many psychologists, "
            "staff or users the system has — and questions about the system "
            "itself. Answering one of those with a child count would be "
            "wrong; use this instead."),
        # `reason` is telemetry, not logic — the response is the same fixed
        # copy either way. Requiring it turned the one case in 28 where the
        # model omitted it into a failed turn, so it defaults instead.
        "schema": {"reason": {"enum": ["greeting_or_closing", "general_knowledge",
                                       "unsupported"],
                              "required": False}},
        "echo": lambda a: "",
        "resolve": _resolve_direct,
    },
}


def ollama_payload():
    """The tools array for /api/chat, derived from REGISTRY.

    Built rather than hand-written so a tool cannot be added to one and
    forgotten in the other.
    """
    out = []
    for name, spec in REGISTRY.items():
        props, required = {}, []
        for param, meta in spec["schema"].items():
            prop = {"type": "string"}
            if "enum" in meta:
                prop["enum"] = meta["enum"]
            props[param] = prop
            if meta.get("required"):
                required.append(param)
        out.append({"type": "function", "function": {
            "name": name, "description": spec["description"],
            "parameters": {"type": "object", "properties": props,
                           "required": required}}})
    return out
