"""The local launcher has to bring up the model server, and bind it safely.

`run-local.bat` started the API and the frontend and left Ollama to whoever
remembered. So the assistant, the chatbot, the briefs and the self-report
detector were all dead on a fresh machine, and said so only as a failed
request from inside a screen.

The binding is the part with teeth. Ollama listens on 0.0.0.0 by default,
which puts an unauthenticated model server on whatever network the laptop is
joined to — a café, a campus, an office. `OLLAMA_HOST=127.0.0.1` is the line
that stops that, and it is one edit away from being lost, so it is asserted
here rather than only written down.

The other two are performance settings measured on this machine and recorded
in CLAUDE.md: the model stays resident between calls, and one generation runs
at a time because concurrent runs on four cores are slower rather than
parallel.
"""
from pathlib import Path

from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[3]


def _read(name):
    return (ROOT / name).read_text(encoding="utf-8", errors="replace")


class RunLocalStartsTheModelServerTest(SimpleTestCase):
    def test_the_launcher_calls_the_ollama_script(self):
        self.assertIn("start-ollama.bat", _read("run-local.bat"))

    def test_the_ollama_script_exists(self):
        self.assertTrue((ROOT / "start-ollama.bat").exists())


class TheModelServerIsBoundToLocalhostTest(SimpleTestCase):
    """Ollama binds 0.0.0.0 unless told otherwise."""

    def setUp(self):
        self.script = _read("start-ollama.bat")

    def test_it_binds_loopback_only(self):
        self.assertIn("OLLAMA_HOST=127.0.0.1", self.script)

    def test_it_never_asks_for_every_interface(self):
        self.assertNotIn("OLLAMA_HOST=0.0.0.0", self.script)

    def test_it_notices_a_server_somebody_else_left_wide_open(self):
        """The tray app starts its own server and this script then stands
        aside — so the safe binding silently does not apply. Saying so is the
        only thing it can usefully do about it."""
        self.assertIn("0.0.0.0:11434", self.script)

    def test_it_keeps_the_model_resident_between_calls(self):
        # Measured: a cold load costs 12-16s and evicting between calls makes
        # every request pay it.
        self.assertIn("OLLAMA_KEEP_ALIVE=-1", self.script)

    def test_it_runs_one_generation_at_a_time(self):
        self.assertIn("OLLAMA_NUM_PARALLEL=1", self.script)

    def test_it_keeps_one_model_loaded_not_several(self):
        # docs/LOCAL-SETUP.md has asked for this since the assistant was
        # built; two resident 2 GB models on this machine is how it starts
        # swapping.
        self.assertIn("OLLAMA_MAX_LOADED_MODELS=1", self.script)


class TheLauncherDegradesRatherThanFailsTest(SimpleTestCase):
    """A machine with no Ollama still runs the whole case-management system.

    Only the assistant features need it, so a missing model server is a
    warning. Stopping here would make an optional dependency mandatory.
    """

    def setUp(self):
        self.script = _read("start-ollama.bat")

    def test_it_never_reports_failure_to_the_caller(self):
        self.assertNotIn("exit /b 1", self.script)

    def test_it_looks_for_ollama_before_using_it(self):
        self.assertIn("where ollama", self.script.lower())

    def test_it_says_when_the_model_has_never_been_pulled(self):
        # Installed but empty fails at the first question rather than here,
        # which is a long way from the cause.
        self.assertIn("qwen2.5:3b-instruct", self.script)

    def test_it_checks_whether_a_server_is_already_listening(self):
        # Starting a second one just fails noisily on a bound port, and the
        # Ollama tray app may already have started the first.
        self.assertIn("11434", self.script)
