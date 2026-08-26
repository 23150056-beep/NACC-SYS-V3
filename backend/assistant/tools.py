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
import re

# Enum values the model reached for that were not in the enum. Deterministic,
# instant, free — and the single change that took measured accuracy from 91%
# to 100% on the spike's case set.
ALIASES = {
    "when": {
        "bukas": "tomorrow", "ngayon": "today", "kahapon": "today",
        "ngayong linggo": "this_week", "susunod na linggo": "next_week",
        "this week": "this_week", "next week": "next_week",
    },
    "status": {
        "aktibo": "active", "buhay": "active", "tapos": "terminated",
        "lahat": "any", "all": "any",
    },
}

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


# --- resolvers ------------------------------------------------------------
# Each takes (request, validated args) and returns a plain dict the frontend
# renders. The model never sees any of this — which is precisely why a
# hallucinated child name is impossible here: names come out of the database.
#
# Scope is taken from request.user through the same helper the rest of the app
# uses. No resolver reads scope from the model's arguments.

_WINDOWS = {"today": (0, 1), "tomorrow": (1, 2),
            "this_week": (0, 7), "next_week": (7, 14)}

DIRECT_REPLY = ("I can answer questions about your schedule, your children, "
                "and who needs follow-up. I can't answer anything else.")


def _scope(request):
    from assistant.views import _visible_children      # local: avoids a cycle
    return _visible_children(request)


def _resolve_appointments(request, args):
    from django.utils import timezone
    from datetime import timedelta
    from scheduling.models import Appointment

    offset, span = _WINDOWS[args["when"]]
    today = timezone.localdate()
    start, end = today + timedelta(days=offset), today + timedelta(days=offset + span - offset if span else 1)
    end = today + timedelta(days=span)
    appts = (Appointment.objects
             .filter(psychologist=request.user, status=Appointment.SCHEDULED,
                     start__date__gte=start, start__date__lt=end)
             .select_related("child").order_by("start"))
    return {"kind": "appointments", "when": args["when"], "items": [
        {"child": a.child.fullname, "when": timezone.localtime(a.start).strftime("%a %d %b, %H:%M"),
         "purpose": a.get_purpose_display()} for a in appts]}


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


def _search_words(term):
    """Words worth matching on, singular forms included.

    Short words are dropped: "of" and "the" appear inside so many records that
    matching them would return the whole caseload as a false hit.
    """
    words = {w for w in re.findall(r"[\w']+", term.lower()) if len(w) >= 4}
    return sorted(words | {_singular(w) for w in words})


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

    matches = list(_scope(request).filter(fullname__icontains=args["name"])[:6])
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


def _resolve_direct(request, args):
    return {"kind": "message", "reason": args.get("reason", "unsupported"),
            "text": DIRECT_REPLY}


REGISTRY = {
    "list_my_appointments": {
        "description": (
            "The signed-in user's own schedule: appointments, sessions, visits, "
            "and WHO THEY ARE SEEING on a given day. Use for any question about "
            "the calendar or schedule. Do NOT use this to search for children."),
        "schema": {"when": {"enum": ["today", "tomorrow", "this_week", "next_week"],
                            "required": True}},
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
            "Find children whose presenting concern or problem matches a "
            "description, for example 'school refusal', 'anxiety', 'withdrawn'. "
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
