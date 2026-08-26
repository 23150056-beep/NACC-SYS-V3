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


# --- resolvers ------------------------------------------------------------
# Each takes (request, args) and returns a plain dict the frontend renders.
# They are thin on purpose: the querysets and the scoping already exist.

def _resolve_appointments(request, args):
    from assistant.views import _visible_children          # local: avoids a cycle
    return {"when": args["when"], "children": _visible_children(request)}


def _resolve_count(request, args):
    from assistant.views import _visible_children
    return {"status": args["status"], "children": _visible_children(request)}


def _resolve_concern(request, args):
    from assistant.views import _visible_children
    return {"concern": args["concern"], "children": _visible_children(request)}


def _resolve_summary(request, args):
    from assistant.views import _visible_children
    return {"name": args["name"], "children": _visible_children(request)}


def _resolve_care_gaps(request, args):
    from assistant.views import _visible_children
    return {"children": _visible_children(request)}


def _resolve_direct(request, args):
    return {"reason": args.get("reason", "unsupported")}


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
            "How many children are in the user's caseload. Use for questions "
            "starting 'how many'. Do NOT use for schedule questions."),
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
            "this user's schedule, children or caseload."),
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
