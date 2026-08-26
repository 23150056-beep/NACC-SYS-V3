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

from assistant import evaluation, prompts
from assistant.models import AssistantSetting
from assistant.services import AIUnavailable, get_ai_client
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

_TAGALOG_HINT = ("naki", "nag-", "ang ", " sa ", " ng ", "mga ", "hindi", "bata")


def _looks_taglish(text):
    low = text.lower()
    return any(h in low for h in _TAGALOG_HINT)


class Command(BaseCommand):
    help = "Evaluate the assistant's drafting output against real records."

    def add_arguments(self, parser):
        parser.add_argument("--feature", choices=["brief", "polish", "all"],
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
                  "repeated words": 0, "language drift": 0}

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
                flags = self._score(prompt, text, expect_english=True)
                for key in flags:
                    counts[key] += 1
                self._report(rep, ms, flags)

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
                self._report(rep, ms, flags, sample=text)

        return ("REMARK POLISH", runs, counts, self._median(latencies))

    # -- output -----------------------------------------------------------

    def _report(self, rep, ms, flags, sample=None):
        if not flags:
            self.stdout.write(f"    rep{rep}: clean  ({ms} ms)")
            return
        parts = ", ".join(f"{k}={v}" for k, v in flags.items())
        self.stdout.write(f"    rep{rep}: {parts}  ({ms} ms)")
        if sample:
            self.stdout.write(f"        out: {sample.strip()[:140]}")

    @staticmethod
    def _median(values):
        if not values:
            return 0
        ordered = sorted(values)
        return ordered[len(ordered) // 2]
