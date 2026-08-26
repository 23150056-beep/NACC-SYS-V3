"""Score what the assistant actually writes, against real records.

This is an instrument, not a gate. It needs a running Ollama, so it can never
live in the test suite — but without it, "the briefs seem fine" is an
impression rather than a number, and an impression is how a hallucinated child
name reached a clinical draft unnoticed.

    manage.py ai_eval                      # every feature, 2 reps
    manage.py ai_eval --feature polish     # one feature
    manage.py ai_eval --reps 5 --limit 6   # more evidence, more children
"""
import time

from django.core.management.base import BaseCommand

from assistant import evaluation, prompts, tools
from assistant.models import AssistantSetting
from assistant.services import AIUnavailable, get_ai_client
from accounts.models import Role
from children.models import Child

# Fixed polish inputs: Taglish as the notes are actually written, heavy Tagalog,
# and an English control. The control is what tells us whether a failure is
# about language or about the feature.
POLISH_CASES = [
    ("taglish",
     "Settling in well. Nakikisalamuha na sa ibang bata during recreation."),
    ("heavy tagalog",
     "Nag-aalala pa rin tungkol sa school. Hindi masyado nagsasalita ngayon."),
    ("english control",
     "Settling in well. Mixing with the other children during recreation."),
]


# Chat cases, in both registers. `expect_hits` is the column that matters: a
# question that routes perfectly and then returns nothing is the failure this
# eval exists to catch. Searching the phrase "school refusal" as a substring
# scored 100% on routing and 0% on answers for a full day, because nothing
# measured the second half.
CHAT_CASES = [
    ("appointments en", "Who am I seeing tomorrow?", "list_my_appointments", False),
    ("appointments tl", "Sino ang makikita ko bukas?", "list_my_appointments", False),
    ("count en", "How many children am I handling?", "count_my_children", True),
    ("count tl", "Ilan ang mga bata ko?", "count_my_children", True),
    ("concern en", "Any children with school refusal?",
     "search_children_by_concern", True),
    ("concern tl", "Sino ang mga bata na ayaw pumasok sa eskwela?",
     "search_children_by_concern", True),
    ("concern sleep", "Who has trouble sleeping?",
     "search_children_by_concern", True),
    ("concern plural", "Any kids struggling with emotions?",
     "search_children_by_concern", True),
    ("gaps en", "Who still needs a follow-up?", "list_care_gaps", False),
    ("gaps tl", "Sino ang kailangan ng follow-up?", "list_care_gaps", False),
    ("chitchat", "Good morning!", "answer_directly", False),
    # Regression: seen in the browser answering "40 active children".
    ("staff count en", "how many psychologist are in the system?",
     "answer_directly", False),
    ("staff count tl", "Ilan ang mga psychologist dito?", "answer_directly", False),
]


class _EvalRequest:
    """The two attributes the scope helper reads. A management command has no
    real request, and scope must still come from a user rather than a flag."""

    def __init__(self, user):
        self.user = user


FEELING_Q = "How are you feeling this week?"
WORRY_Q = "Is there anything worrying you?"

# Hand-labelled (question, answer) pairs, every string taken from the live
# database. The label is a human judgement, not ground truth from the agency.
# Both columns matter: a detector that flags everything has perfect recall and
# is worthless, so false alarms are scored too.
SELF_REPORT_CASES = [
    ("tl distress", FEELING_Q, "Gusto ko na umuwi. Lagi akong umiiyak sa gabi.", True),
    ("tl distress", WORRY_Q, "Hindi ko masabi kasi baka magalit sila. Masakit ang dibdib ko.", True),
    ("tl distress", FEELING_Q, "I feel alone. Ayaw ko na dito, gusto ko na lang matulog.", True),
    ("mixed distress", WORRY_Q, "Nobody listens to me here. Wala akong makausap.", True),
    ("ilocano distress", FEELING_Q, "Mabutbuteng. I am scared but I don't tell them.", True),
    ("ilocano distress", WORRY_Q, "Adda met bassit nga problema but I don't want to say.", True),
    ("ambiguous", FEELING_Q, "Sometimes I cannot sleep. Naiisip ko yung bahay namin.", True),
    ("calm control", FEELING_Q, "I feel safe. Ang bait ng nag-aalaga sa akin.", False),
    ("calm control", FEELING_Q, "Okay lang. I like the food and my bed.", False),
    ("calm control", FEELING_Q, "Masaya naman ako dito. May kaibigan na ako.", False),
    ("ilocano calm", FEELING_Q, "Naimbag met. I can sleep at night now.", False),
    ("calm control", FEELING_Q, "I miss my sister. But the people here are kind.", False),
]


_TAGALOG_HINT = ("naki", "nag-", "ang ", " sa ", " ng ", "mga ", "hindi", "bata")


def _looks_taglish(text):
    low = text.lower()
    return any(h in low for h in _TAGALOG_HINT)


class Command(BaseCommand):
    help = "Evaluate the assistant's drafting output against real records."

    def add_arguments(self, parser):
        parser.add_argument("--feature",
                            choices=["brief", "polish", "chat", "self_report", "all"],
                            default="all")
        parser.add_argument("--reps", type=int, default=2,
                            help="Runs per case; the model is not deterministic.")
        parser.add_argument("--limit", type=int, default=3,
                            help="Children to sample for briefs.")

    def handle(self, *args, **options):
        cfg = AssistantSetting.load()
        if not cfg.enabled:
            self.stdout.write("The assistant is switched off — nothing to evaluate.")
            raise SystemExit(1)

        self.client = get_ai_client()
        self.stdout.write(f"Model: {cfg.model_name}   reps: {options['reps']}\n")

        totals = []
        if options["feature"] in ("brief", "all"):
            totals.append(self._briefs(options["reps"], options["limit"]))
        if options["feature"] in ("polish", "all"):
            totals.append(self._polish(options["reps"]))
        if options["feature"] in ("chat", "all"):
            totals.append(self._chat(options["reps"]))
        if options["feature"] in ("self_report", "all"):
            totals.append(self._self_report(options["reps"]))

        self.stdout.write("\n" + "=" * 62)
        self.stdout.write("SUMMARY")
        for name, runs, flags, latency in totals:
            if not runs:
                continue
            self.stdout.write(f"\n{name}  ({runs} runs, median {latency} ms)")
            for label, n in flags.items():
                pct = 100 * n / runs
                self.stdout.write(f"  {label:22} {n}/{runs}  ({pct:.0f}%)")

    # -- features ---------------------------------------------------------

    def _generate(self, prompt, system):
        started = time.monotonic()
        text = self.client.generate(prompt, system=system)
        return text, int((time.monotonic() - started) * 1000)

    def _score(self, prompt, text, expect_english):
        flags = {}
        names = evaluation.invented_names(prompt, text)
        if names:
            flags["invented names"] = names
        repeats = evaluation.repeated_lines(text)
        if repeats:
            flags["repeated lines"] = repeats
        stutters = evaluation.repeated_phrases(text)
        if stutters:
            flags["repeated words"] = stutters
        if expect_english:
            drift = evaluation.language_drift(text)
            if drift:
                flags["language drift"] = drift
        return flags

    def _briefs(self, reps, limit):
        children = list(Child.objects.filter(remarks__isnull=False)
                        .distinct().order_by("id")[:limit])
        self.stdout.write("\n" + "=" * 62)
        self.stdout.write(f"BRIEFS — {len(children)} children x {reps} reps")

        runs, latencies = 0, []
        counts = {"invented names": 0, "repeated lines": 0,
                  "repeated words": 0}

        for child in children:
            prompt = prompts.build_brief_prompt(child)
            tag = "taglish" if _looks_taglish(prompt) else "english"
            self.stdout.write(f"\n  {child.fullname} (id={child.id}) [{tag}]")
            for rep in range(reps):
                try:
                    text, ms = self._generate(prompt, prompts.BRIEF_SYSTEM)
                except AIUnavailable as exc:
                    self.stdout.write(f"    rep{rep}: UNAVAILABLE — {exc}")
                    continue
                runs += 1
                latencies.append(ms)
                # BRIEF_SYSTEM does not ask for English — it asks for the
                # facts it was given. A brief quoting a Taglish remark is
                # correct, so scoring drift here measured a requirement that
                # does not exist and reported 8% against briefs that were fine.
                flags = self._score(prompt, text, expect_english=False)
                for key in flags:
                    counts[key] += 1
                self._report(rep, ms, flags, text=text)

        return ("BRIEFS", runs, counts, self._median(latencies))

    def _polish(self, reps):
        self.stdout.write("\n" + "=" * 62)
        self.stdout.write(f"REMARK POLISH — {len(POLISH_CASES)} cases x {reps} reps")

        runs, latencies = 0, []
        counts = {"invented names": 0, "repeated lines": 0,
                  "repeated words": 0, "language drift": 0}

        for label, raw in POLISH_CASES:
            prompt = prompts.build_remark_prompt(raw)
            self.stdout.write(f"\n  [{label}] {raw[:60]}")
            for rep in range(reps):
                try:
                    text, ms = self._generate(prompt, prompts.REMARK_POLISH_SYSTEM)
                except AIUnavailable as exc:
                    self.stdout.write(f"    rep{rep}: UNAVAILABLE — {exc}")
                    continue
                runs += 1
                latencies.append(ms)
                flags = self._score(prompt, text, expect_english=True)
                for key in flags:
                    counts[key] += 1
                self._report(rep, ms, flags, sample=text, text=text)

        return ("REMARK POLISH", runs, counts, self._median(latencies))


    def _chat(self, reps):
        """Route a question, validate it, and run the resolver for real.

        The resolver runs against the live database under a real psychologist's
        scope, so "found nothing" is measured rather than assumed.
        """
        user = (Child.objects.exclude(assigned_psychologist=None)
                .values_list("assigned_psychologist", flat=True).first())
        if user is None:
            self.stdout.write("\nCHAT — no psychologist has a caseload; skipped.")
            return ("chat", 0, {}, 0)
        from django.contrib.auth import get_user_model
        request = _EvalRequest(get_user_model().objects.get(pk=user))

        self.stdout.write("\n" + "=" * 62)
        self.stdout.write(f"CHAT — {len(CHAT_CASES)} cases x {reps} reps")
        self.stdout.write(f"Caller: {request.user.email}")

        runs, flags, latencies = 0, {}, []
        payload = tools.ollama_payload()
        for label, question, expected, expect_hits in CHAT_CASES:
            self.stdout.write(f"\n  {label}: {question}")
            for rep in range(1, reps + 1):
                started = time.monotonic()
                try:
                    tool, raw = self.client.choose_tool(
                        question, payload, prompts.CHAT_SYSTEM)
                except AIUnavailable as exc:
                    self.stdout.write(f"    rep{rep}: unavailable — {exc}")
                    continue
                ms = int((time.monotonic() - started) * 1000)
                latencies.append(ms)
                runs += 1

                found = {}
                if tool != expected:
                    found["wrong tool"] = [f"{tool or 'prose'} != {expected}"]
                call = tools.validate(tool or "answer_directly", raw)
                call = tools.correct_obvious_misroute(question, call)
                if not call.ok:
                    found["rejected"] = [call.error]
                elif expect_hits:
                    result = tools.REGISTRY[call.tool]["resolve"](request, call.args)
                    n = result.get("count", len(result.get("items", [])))
                    if not n:
                        # The silent failure: a confident empty answer.
                        found["empty answer"] = [f"{call.args or 'no args'}"]
                for key, items in found.items():
                    flags.setdefault(key, 0)
                    flags[key] += 1
                self._report(rep, ms, {k: v for k, v in found.items()})

        latencies.sort()
        median = latencies[len(latencies) // 2] if latencies else 0
        return ("CHAT", runs, flags, median)


    def _self_report(self, reps):
        """Score the model detector against hand-labelled pairs.

        Reports misses AND false alarms. A detector that flags everything has
        perfect recall and is worthless, so both columns are printed.
        """
        from clinical.self_report_model_check import _parse

        self.stdout.write("\n" + "=" * 62)
        self.stdout.write(f"SELF-REPORT - {len(SELF_REPORT_CASES)} cases x {reps} reps")

        runs, flags, latencies = 0, {}, []
        for label, question, answer, expected in SELF_REPORT_CASES:
            self.stdout.write(f"\n  {label}: {answer[:56]}")
            for rep in range(1, reps + 1):
                started = time.monotonic()
                try:
                    reply = self.client.generate(
                        prompts.build_self_report_prompt(question, answer),
                        system=prompts.SELF_REPORT_SYSTEM)
                except AIUnavailable as exc:
                    self.stdout.write(f"    rep{rep}: unavailable - {exc}")
                    continue
                ms = int((time.monotonic() - started) * 1000)
                latencies.append(ms)
                runs += 1

                got = _parse(reply) is not None
                found = {}
                if expected and not got:
                    found["MISS"] = [answer[:48]]
                elif got and not expected:
                    found["false alarm"] = [answer[:48]]
                for key in found:
                    flags[key] = flags.get(key, 0) + 1
                self._report(rep, ms, found, sample=str(reply))

        latencies.sort()
        median = latencies[len(latencies) // 2] if latencies else 0
        return ("SELF-REPORT", runs, flags, median)

    # -- output -----------------------------------------------------------

    def _report(self, rep, ms, flags, sample=None, text=None):
        if not flags:
            self.stdout.write(f"    rep{rep}: clean  ({ms} ms)")
            return
        parts = ", ".join(f"{k}={v}" for k, v in flags.items())
        self.stdout.write(f"    rep{rep}: {parts}  ({ms} ms)")
        # A flag without its surrounding text is a number nobody can act on —
        # it forces whoever reads the run to go and reproduce it by hand, which
        # is how two false-positive detectors survived long enough to put wrong
        # rates in a report. Every flag shows where it fired.
        if text:
            for label, items in flags.items():
                if label == "language drift":
                    continue          # markers are scattered; the sample below shows them
                for item in items[:3]:
                    self.stdout.write(f"        {label}: {self._context(text, item)}")
        if sample:
            self.stdout.write(f"        out: {sample.strip()[:140]}")

    @staticmethod
    def _context(text, needle, width=60):
        """The offending phrase with enough either side to judge it."""
        flat = " ".join(text.split())
        i = flat.find(needle)
        if i < 0:
            return f"(…{needle}…)"
        start = max(0, i - width // 2)
        return "…" + flat[start:i + len(needle) + width // 2] + "…"

    @staticmethod
    def _median(values):
        if not values:
            return 0
        ordered = sorted(values)
        return ordered[len(ordered) // 2]
