# Free Secure Web Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Put NACC SYS V3 on a public URL for free, with the real Neon accounts and a fictional caseload, without touching the live Render deployment.

**Architecture:** Two phases. Phase 1 deploys the application from the `local-ver` repo to new Render services against an isolated Neon branch, with no model anywhere — a complete working demo on its own. Phase 2 adds the chatbot through Cloudflare Workers AI's OpenAI-compatible endpoint, behind a guard that makes a hosted provider impossible to enable by accident.

**Tech Stack:** Django 5.1 + DRF, React 18 + Vite, Render (free), Neon PostgreSQL (branch), Cloudflare R2, Cloudflare Workers AI (`@cf/meta/llama-4-scout-17b-16e-instruct`).

**Spec:** `docs/superpowers/specs/2026-08-27-free-secure-web-deployment-design.md`

## Global Constraints

- **Commit authorship:** every commit authored **and** committed by `Reynold <jreynoldcanedo@gmail.com>`. No Claude attribution, no `Co-Authored-By`, no model name in any commit message, PR body, or code comment.
- **Never push to `origin`.** `git push` goes to `local-ver` and is correct; `git push origin` deploys the live system and requires asking first.
- **Python is `backend/.venv/Scripts/python.exe`**, never `.venv/bin/python`.
- **`seed_demo_data` is never run against a hosted database and its guards are never weakened.**
- **The live Neon `main` branch is never written to.** Every database operation targets the branch.
- **No object is copied from the live R2 bucket.** The demo bucket starts and stays empty.
- **The hosted model is chatbot-only.** Briefs, remark polish, document summaries and the self-report model detector stay off until each is measured separately.
- **The model must return structured `tool_calls`.** `@cf/qwen/qwen3-30b-a3b-fp8` returns them as raw `<tool_call>` text and must not be used.
- Before any commit: `cd backend && .venv/Scripts/python.exe manage.py test` and `cd frontend && npm run lint && npm run build`.

---

## File Structure

| File | Responsibility |
|---|---|
| `render.yaml` | **Modify.** Rename both services so they cannot collide with the live ones. |
| `CLAUDE.md` | **Modify.** Correct the now-false "`git push` is safe" line. |
| `backend/children/management/commands/export_demo_data.py` | **Create.** Dump the fictional caseload to a fixture, locally only. |
| `backend/children/management/commands/import_demo_data.py` | **Create.** Load that fixture into a hosted branch and reassign children to real accounts. Phase 1's only new runtime code. |
| `backend/assistant/services.py` | **Modify.** Add `OpenAICompatibleClient`; teach `get_ai_client()` to choose. Phase 2. |
| `backend/config/settings.py` | **Modify.** Read the hosted-model environment variables. Phase 2. |
| `backend/assistant/views.py` | **Modify.** Throttle scopes on the assistant endpoints; the model reachability endpoint. Phase 2. |
| `backend/assistant/urls.py` | **Modify.** Route for the reachability check. Phase 2. |
| `docs/CLOUD-DEPLOYMENT.md` | **Modify.** A demo-deployment section: the manual Neon, R2 and Render steps. |

---

# PHASE 1 — the application

## Task 1: Rename the services so they cannot collide

`render.yaml` declares `nacc-v3-api` and `nacc-v3-web` — the exact names of the live services. Creating a Blueprint from this repo on the same Render account would clash with production. This must land before anyone opens the Render dashboard.

**Files:**
- Modify: `render.yaml`
- Modify: `CLAUDE.md`

**Interfaces:**
- Consumes: nothing.
- Produces: service names `nacc-v3-demo-api` and `nacc-v3-demo-web`.

- [ ] **Step 1: Rename both services**

In `render.yaml`, change `name: nacc-v3-api` to `name: nacc-v3-demo-api`, and `name: nacc-v3-web` to `name: nacc-v3-demo-web`.

- [ ] **Step 2: Replace the blueprint's opening comment**

The current header describes the live deployment. Replace the comment block above `services:` with:

```yaml
# NACC SYS V3 — Render blueprint for the DEMO deployment.
#
# This file lives in NACC-SYS-V3.1-LOCAL-VER and creates services named
# nacc-v3-demo-*. The LIVE services (nacc-v3-api, nacc-v3-web) are created from
# a different repository and are not affected by anything here.
#
# The names differ deliberately. Render service names are unique per workspace,
# so reusing the live names would collide with production.
#
# DATABASE_URL must be a Neon BRANCH connection string, never main. The branch
# exists so the demo inherits the real user accounts while its writes — and the
# migrations in this repo that the live deployment does not have — never reach
# production.
#
# The R2 variables must point at an empty demo bucket. No object is copied from
# the live bucket: the demo has no reports, consent scans or child photographs
# because it has none at all.
#
# ⚠️  Free plan: services sleep after ~15 minutes idle, so the first request
# after a quiet period takes ~60 seconds while the container wakes.
```

- [ ] **Step 3: Correct the push rule in CLAUDE.md**

In the "Getting changes onto GitHub" section, replace the sentence beginning "is correct and goes to the local-version repo" with:

```markdown
is correct and goes to the local-version repo. **Once the demo Blueprint is
connected, that push also auto-deploys the demo** at nacc-v3-demo-*. It still
cannot touch the live services. **Do not `git push origin`** — the owner has
said he does not want Render touched, and that push is what deploys it.
Pushing there needs asking first, in so many words.
```

- [ ] **Step 4: Verify no live name survives**

```bash
grep -n "nacc-v3-api\|nacc-v3-web" render.yaml
```
Expected: no output. Any match is a service that would collide with production.

- [ ] **Step 5: Commit**

```bash
git add render.yaml CLAUDE.md
git -c user.email=jreynoldcanedo@gmail.com commit --author="Reynold <jreynoldcanedo@gmail.com>" -m "Name the demo services so they cannot collide with production

render.yaml declared nacc-v3-api and nacc-v3-web — the exact names of the live
services. A Blueprint created from this repo on the same Render account would
have clashed with production, which is a poor way to discover a naming rule.

Also corrects the push note in the handbook. Once the demo Blueprint is
connected, a bare git push auto-deploys the demo; calling that push simply
'safe' would send the next session's half-finished branch to a public URL."
```

---

## Task 2: Export the fictional caseload

`seed_demo_data` refuses to run against a hosted database, and that guard stays. The demo children reach the branch as a fixture instead.

**Files:**
- Create: `backend/children/management/commands/export_demo_data.py`
- Test: `backend/children/tests/test_demo_transfer.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `manage.py export_demo_data [--output PATH]`, writing a JSON fixture. Default path `demo_fixture.json` in the current directory. Users are **excluded**.

- [ ] **Step 1: Write the failing test**

Create `backend/children/tests/test_demo_transfer.py`:

```python
"""Moving the fictional caseload to a hosted branch.

seed_demo_data refuses to run against a hosted database and that guard is not
weakened, so the demo children travel as a fixture instead.
"""
import json
import tempfile
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from accounts.models import Role
from children.models import Child

User = get_user_model()


class ExportDemoDataTest(TestCase):
    def setUp(self):
        role = Role.objects.create(role_name=Role.PSYCHOLOGIST)
        self.psy = User.objects.create_user(
            email="p@racco1.gov.ph", username="p", password="pass1234", role=role)
        Child.objects.create(fullname="Maria Santos", assigned_psychologist=self.psy)

    def _export(self):
        path = Path(tempfile.mkdtemp()) / "demo.json"
        call_command("export_demo_data", output=str(path))
        return json.loads(path.read_text(encoding="utf-8"))

    def test_writes_the_children(self):
        models = {row["model"] for row in self._export()}
        self.assertIn("children.child", models)

    def test_excludes_users(self):
        # Importing users would collide with the real accounts on the branch,
        # which are the entire reason for using that database.
        models = {row["model"] for row in self._export()}
        self.assertNotIn("accounts.user", models)
        self.assertNotIn("accounts.role", models)

    def test_excludes_assistant_jobs(self):
        # Audit rows carry the questions people typed, which name children.
        models = {row["model"] for row in self._export()}
        self.assertNotIn("assistant.assistantjob", models)

    def test_reports_what_it_wrote(self):
        from io import StringIO
        out = StringIO()
        path = Path(tempfile.mkdtemp()) / "demo.json"
        call_command("export_demo_data", output=str(path), stdout=out)
        self.assertIn("1 children", out.getvalue())
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd backend && ./.venv/Scripts/python.exe manage.py test children.tests.test_demo_transfer`
Expected: FAIL — `CommandError: Unknown command: 'export_demo_data'`

- [ ] **Step 3: Write the command**

Create `backend/children/management/commands/export_demo_data.py`:

```python
"""Dump the fictional caseload so it can be loaded into a hosted branch.

seed_demo_data refuses to run against a hosted database — deliberately, and
that guard stays. Its comment gives the reason: mixing fictional records into
real case files is "not a data loss, something worse: a file that cannot be
trusted." So the demo children travel as a fixture instead.

Users are excluded. The branch already holds the real accounts, and importing
the seeder's four would collide on the unique email.
"""
from django.core.management import call_command
from django.core.management.base import BaseCommand

# Everything seed_demo_data creates, minus anything identifying a real person.
DEMO_MODELS = [
    "children.Child",
    "children.Guardian",
    "clinical.AgencyFormTemplate",
    "clinical.InstrumentCatalog",
    "clinical.ConsentRecord",
    "clinical.PreAssessment",
    "clinical.ProblemEntry",
    "clinical.ResultEntry",
    "clinical.TreatmentPlan",
    "clinical.RemarkNote",
    "clinical.OpinionnaireInvite",
    "clinical.SelfReportFlag",
    "scheduling.Appointment",
]


class Command(BaseCommand):
    help = "Dump the fictional caseload to a fixture for a demo deployment."

    def add_arguments(self, parser):
        parser.add_argument("--output", default="demo_fixture.json",
                            help="Where to write the fixture.")

    def handle(self, *args, **options):
        path = options["output"]
        with open(path, "w", encoding="utf-8") as handle:
            call_command("dumpdata", *DEMO_MODELS, indent=2, stdout=handle)

        from children.models import Child
        self.stdout.write(
            f"export_demo_data: {Child.objects.count()} children written to {path}. "
            "Users are excluded on purpose.")
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && ./.venv/Scripts/python.exe manage.py test children.tests.test_demo_transfer`
Expected: PASS.

- [ ] **Step 5: Export the real fixture and check its size**

```bash
cd backend && ./.venv/Scripts/python.exe manage.py export_demo_data --output ../demo_fixture.json
ls -lh ../demo_fixture.json
```

Expected: about 40 children and a file of a few hundred kilobytes. **Do not commit this fixture** — add `demo_fixture.json` to `.gitignore` in the same commit.

- [ ] **Step 6: Commit**

```bash
git add backend/children/management/commands/export_demo_data.py backend/children/tests/test_demo_transfer.py .gitignore
git -c user.email=jreynoldcanedo@gmail.com commit --author="Reynold <jreynoldcanedo@gmail.com>" -m "Export the fictional caseload as a fixture

seed_demo_data refuses to run against a hosted database and that guard is not
weakened — its own comment says mixing fictional records into real case files
is 'not a data loss, something worse: a file that cannot be trusted'. So the
demo children travel as a fixture instead.

Users are excluded. The branch already holds the real accounts, which are the
reason for using that database at all, and importing the seeder's four would
collide on the unique email. Assistant jobs are excluded too: they store the
questions people typed, and those name children."
```

---

## Task 3: Import into the branch, and reassign to real accounts

**Files:**
- Create: `backend/children/management/commands/import_demo_data.py`
- Test: `backend/children/tests/test_demo_transfer.py` (append)

**Interfaces:**
- Consumes: the fixture from Task 2.
- Produces: `manage.py import_demo_data --fixture PATH [--clear] [--set-password EMAIL:PASSWORD]`.

- [ ] **Step 1: Write the failing test**

Append to `backend/children/tests/test_demo_transfer.py`:

```python
class ImportDemoDataTest(TestCase):
    """The import runs against a branch that already holds the real accounts."""

    def setUp(self):
        self.role = Role.objects.create(role_name=Role.PSYCHOLOGIST)
        # Two "real" accounts, as a Neon branch would carry.
        self.real_a = User.objects.create_user(
            email="real.a@racco1.gov.ph", username="ra", password="pass1234",
            role=self.role)
        self.real_b = User.objects.create_user(
            email="real.b@racco1.gov.ph", username="rb", password="pass1234",
            role=self.role)
        # A seeder account that must NOT survive as an assignee.
        self.seeded = User.objects.create_user(
            email="m.bulan@racco1.gov.ph", username="mb", password="pass1234",
            role=self.role)
        self.fixture = Path(tempfile.mkdtemp()) / "demo.json"

    def _write_fixture(self, count=4):
        rows = []
        for i in range(count):
            rows.append({
                "model": "children.child",
                "pk": 900 + i,
                "fields": {"fullname": f"Demo Child {i}",
                           "assigned_psychologist": self.seeded.pk},
            })
        self.fixture.write_text(json.dumps(rows), encoding="utf-8")

    def test_loads_the_children(self):
        self._write_fixture()
        call_command("import_demo_data", fixture=str(self.fixture))
        self.assertEqual(4, Child.objects.count())

    def test_spreads_them_across_the_real_psychologists(self):
        # The whole point: the demo caseload lands on the accounts that already
        # exist, not on the seeder's invented ones.
        self._write_fixture()
        call_command("import_demo_data", fixture=str(self.fixture))
        assignees = set(Child.objects.values_list(
            "assigned_psychologist__email", flat=True))
        self.assertEqual({"real.a@racco1.gov.ph", "real.b@racco1.gov.ph"}, assignees)

    def test_no_child_is_left_on_a_seeder_account(self):
        self._write_fixture()
        call_command("import_demo_data", fixture=str(self.fixture))
        self.assertEqual(0, Child.objects.filter(
            assigned_psychologist=self.seeded).count())

    def test_clear_removes_existing_children_first(self):
        Child.objects.create(fullname="Pre-existing", assigned_psychologist=self.real_a)
        self._write_fixture()
        call_command("import_demo_data", fixture=str(self.fixture), clear=True)
        self.assertEqual(4, Child.objects.count())
        self.assertFalse(Child.objects.filter(fullname="Pre-existing").exists())

    def test_without_clear_existing_children_survive(self):
        Child.objects.create(fullname="Pre-existing", assigned_psychologist=self.real_a)
        self._write_fixture()
        call_command("import_demo_data", fixture=str(self.fixture))
        self.assertTrue(Child.objects.filter(fullname="Pre-existing").exists())

    def test_can_set_a_known_password_for_one_account(self):
        self._write_fixture()
        call_command("import_demo_data", fixture=str(self.fixture),
                     set_password="real.a@racco1.gov.ph:demo12345")
        self.real_a.refresh_from_db()
        self.assertTrue(self.real_a.check_password("demo12345"))

    def test_refuses_when_no_psychologist_exists(self):
        # Better to stop than to leave every child unassigned and invisible.
        from django.core.management.base import CommandError
        User.objects.filter(role=self.role).delete()
        self._write_fixture()
        with self.assertRaises(CommandError):
            call_command("import_demo_data", fixture=str(self.fixture))
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd backend && ./.venv/Scripts/python.exe manage.py test children.tests.test_demo_transfer`
Expected: FAIL — `Unknown command: 'import_demo_data'`

- [ ] **Step 3: Write the command**

Create `backend/children/management/commands/import_demo_data.py`:

```python
"""Load the fictional caseload into a deployment database.

Intended for a Neon BRANCH that already carries the real user accounts. The
children come from export_demo_data; the accounts are whatever the branch
already holds, which is the reason for branching that database at all.

Every imported child is reassigned to a psychologist that exists here. The
fixture's assignee ids belong to the local machine and mean nothing on the
branch — left alone, every child would point at the wrong person or at nobody.
"""
import json

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import Role
from children.models import Child


class Command(BaseCommand):
    help = "Load the fictional caseload and assign it to real accounts."

    def add_arguments(self, parser):
        parser.add_argument("--fixture", required=True,
                            help="Path to the file written by export_demo_data.")
        parser.add_argument("--clear", action="store_true",
                            help="Delete existing children first.")
        parser.add_argument("--set-password", default="",
                            help="EMAIL:PASSWORD — give one account a known "
                                 "password, for demonstrating with.")

    @transaction.atomic
    def handle(self, *args, **options):
        User = get_user_model()
        psychologists = list(
            User.objects.filter(role__role_name=Role.PSYCHOLOGIST)
            .order_by("pk"))
        if not psychologists:
            raise CommandError(
                "No psychologist accounts here. Importing would leave every "
                "child unassigned and invisible to everyone.")

        if options["clear"]:
            removed = Child.objects.count()
            Child.objects.all().delete()
            self.stdout.write(f"  cleared {removed} existing children")

        with open(options["fixture"], encoding="utf-8") as handle:
            rows = json.load(handle)
        self.stdout.write(f"  fixture holds {len(rows)} rows")
        call_command("loaddata", options["fixture"])

        # Round-robin across whoever is really here. The fixture's assignee ids
        # are local and meaningless on this database.
        imported = list(Child.objects.order_by("pk"))
        for index, child in enumerate(imported):
            child.assigned_psychologist = psychologists[index % len(psychologists)]
        Child.objects.bulk_update(imported, ["assigned_psychologist"])

        if options["set_password"]:
            email, _, password = options["set_password"].partition(":")
            user = User.objects.filter(email=email).first()
            if user is None:
                raise CommandError(f"No account here with the email {email}.")
            user.set_password(password)
            user.must_change_password = False
            user.save()
            self.stdout.write(f"  password set for {email}")

        self.stdout.write(
            f"import_demo_data: {len(imported)} children across "
            f"{len(psychologists)} psychologists.")
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && ./.venv/Scripts/python.exe manage.py test children.tests.test_demo_transfer`
Expected: PASS.

- [ ] **Step 5: Run the whole suite**

Run: `cd backend && ./.venv/Scripts/python.exe manage.py test`
Expected: 666 plus the new tests, all green.

- [ ] **Step 6: Commit**

```bash
git add backend/children/management/commands/import_demo_data.py backend/children/tests/test_demo_transfer.py
git -c user.email=jreynoldcanedo@gmail.com commit --author="Reynold <jreynoldcanedo@gmail.com>" -m "Import the demo caseload onto the accounts that already exist

Every imported child is reassigned round-robin to a psychologist present in the
target database. The fixture's assignee ids belong to the local machine and
mean nothing on a branch — left alone, every child would point at the wrong
person or at nobody at all.

Refuses outright when the target holds no psychologist, rather than importing a
caseload nobody can see.

--set-password gives one account a known password for demonstrating with. It is
run against the branch only; main is never written to."
```

---

## Task 4: Document the manual deployment steps

The Neon, R2 and Render work is done in three dashboards by a person. Written down so it is repeatable and so the dangerous steps are called out.

**Files:**
- Modify: `docs/CLOUD-DEPLOYMENT.md`

- [ ] **Step 1: Append the demo deployment section**

Add at the end of `docs/CLOUD-DEPLOYMENT.md`:

```markdown
## Demo deployment (free, from the local-version repo)

A second, public deployment for showing the system. It shares nothing with the
live one except a Render account and a Neon project.

### 1. Neon — branch, do not reuse

Neon console → the project → **Branches** → **New Branch** from `main`.
Name it `demo`. Copy its **direct** connection string — a host containing
`-pooler` routes through pgbouncer in transaction mode and breaks migrations.

The branch exists so the demo inherits the real user accounts while its writes
never reach production. **Never paste `main`'s connection string into the demo
service.** That single mistake points a public URL at real records.

### 2. Cloudflare R2 — a new, empty bucket

Create `nacc-v3-demo-media` and an API token scoped to it with **Object Read &
Write**. Copy nothing from the live bucket: the demo has no reports, consent
scans or child photographs because it has none at all.

### 3. Render — a new Blueprint

New → Blueprint → connect **NACC-SYS-V3.1-LOCAL-VER** → it reads `render.yaml`
and creates `nacc-v3-demo-api` and `nacc-v3-demo-web`. Set in the dashboard:

- `DATABASE_URL` — the **branch** string from step 1
- the four R2 variables from step 2
- `VITE_API_BASE_URL` on the web service — the API's URL + `/api`, once the API
  has a hostname

### 4. Load the demo caseload

Locally, with `DATABASE_URL` pointing at the **branch**:

```
cd backend
.venv\Scripts\python manage.py export_demo_data --output ..\demo_fixture.json
set DATABASE_URL=<the branch connection string>
.venv\Scripts\python manage.py migrate
.venv\Scripts\python manage.py import_demo_data --fixture ..\demo_fixture.json --clear --set-password <an-account>:<a-password>
```

`--clear` removes any children already on the branch, so the public demo cannot
show a real record. Check the connection string before running it.

### 5. Switch the assistant off

There is no `ASSISTANT_ENABLED` variable and `enabled` defaults to **True**, so
the assistant is on in a fresh deployment. Sign in as an administrator, open
**Settings**, and switch off **Assistant enabled**. Until Phase 2 there is no
model configured, so every AI call returns 503 — harmless, since every screen
absorbs it, but untidy.

The chat pill stays visible either way and answers "unavailable". That is known
and deliberate.

### What is normal and not a fault

- The first visitor after 15 minutes idle waits ~60 seconds while the service wakes.
- Free services sleep. This is the plan, not a misconfiguration.
```

- [ ] **Step 2: Commit**

```bash
git add docs/CLOUD-DEPLOYMENT.md
git -c user.email=jreynoldcanedo@gmail.com commit --author="Reynold <jreynoldcanedo@gmail.com>" -m "Write down the demo deployment's dashboard steps

Three consoles, done by a person, with the two dangerous steps called out: the
Neon connection string must be the branch and never main, and the R2 bucket
must be new and empty rather than the live one.

Also records what looks like a fault and is not — the 60-second wake after
15 minutes idle, and the chat pill that stays visible answering 'unavailable'
until Phase 2."
```

---

**PHASE 1 ENDS HERE.** At this point the demo is deployable and complete: every screen, the real accounts, a fictional caseload, no model anywhere, and no new attack surface. Stop and look at it on a real URL before starting Phase 2.

---

# PHASE 2 — the chatbot, hosted

## Task 5: An OpenAI-compatible client

**Files:**
- Modify: `backend/assistant/services.py`
- Test: `backend/assistant/tests/test_openai_client.py`

**Interfaces:**
- Consumes: `assistant.tools.ollama_payload()`.
- Produces: `OpenAICompatibleClient(base_url, model, token)` with `.generate(prompt, system=...) -> str` and `.choose_tool(question, tool_payload, system) -> (name|None, args_dict)` — the same two-method interface `OllamaClient` already presents, so `views.py` needs no change.

- [ ] **Step 1: Write the failing test**

Create `backend/assistant/tests/test_openai_client.py`:

```python
"""The hosted client speaks /v1/chat/completions.

Every test patches the transport. What matters here is the parsing: a spike
found that one model returns tool calls as raw <tool_call> text rather than in
the structured field, and a client that silently treats that as "no tool call"
would answer every question with a polite refusal while looking healthy.
"""
import json
from unittest.mock import patch

from django.test import SimpleTestCase

from assistant.services import AIUnavailable, OpenAICompatibleClient


def _response(payload):
    class _Fake:
        def read(self):
            return json.dumps(payload).encode()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False
    return _Fake()


class ChooseToolTest(SimpleTestCase):
    def setUp(self):
        self.client = OpenAICompatibleClient(
            "https://example.invalid/v1", "test-model", "token")

    def _call(self, payload):
        with patch("assistant.services.urllib.request.urlopen",
                   return_value=_response(payload)):
            return self.client.choose_tool("How many children?", [], "system")

    def test_reads_a_structured_tool_call(self):
        name, args = self._call({"choices": [{"message": {"tool_calls": [
            {"function": {"name": "count_my_children",
                          "arguments": '{"status": "active"}'}}]}}]})
        self.assertEqual("count_my_children", name)
        self.assertEqual({"status": "active"}, args)

    def test_accepts_arguments_already_parsed(self):
        name, args = self._call({"choices": [{"message": {"tool_calls": [
            {"function": {"name": "list_care_gaps", "arguments": {}}}]}}]})
        self.assertEqual("list_care_gaps", name)
        self.assertEqual({}, args)

    def test_unparseable_arguments_do_not_raise(self):
        name, args = self._call({"choices": [{"message": {"tool_calls": [
            {"function": {"name": "count_my_children",
                          "arguments": "not json at all"}}]}}]})
        self.assertEqual("count_my_children", name)
        self.assertEqual({}, args)

    def test_prose_instead_of_a_tool_call_returns_none(self):
        name, args = self._call({"choices": [{"message": {
            "content": "I think you have several children."}}]})
        self.assertIsNone(name)
        self.assertEqual({}, args)

    def test_an_empty_response_returns_none(self):
        name, _ = self._call({"choices": []})
        self.assertIsNone(name)


class GenerateTest(SimpleTestCase):
    def setUp(self):
        self.client = OpenAICompatibleClient(
            "https://example.invalid/v1", "test-model", "token")

    def test_returns_the_message_content(self):
        with patch("assistant.services.urllib.request.urlopen",
                   return_value=_response({"choices": [
                       {"message": {"content": "  a draft  "}}]})):
            self.assertEqual("a draft", self.client.generate("p", system="s"))

    def test_a_transport_failure_becomes_ai_unavailable(self):
        with patch("assistant.services.urllib.request.urlopen",
                   side_effect=OSError("refused")):
            with self.assertRaises(AIUnavailable):
                self.client.generate("p", system="s")

    def test_choose_tool_failure_becomes_ai_unavailable(self):
        with patch("assistant.services.urllib.request.urlopen",
                   side_effect=OSError("refused")):
            with self.assertRaises(AIUnavailable):
                self.client.choose_tool("q", [], "s")
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd backend && ./.venv/Scripts/python.exe manage.py test assistant.tests.test_openai_client`
Expected: FAIL — `cannot import name 'OpenAICompatibleClient'`

- [ ] **Step 3: Write the client**

Add to `backend/assistant/services.py`, beside `OllamaClient`:

```python
class OpenAICompatibleClient:
    """A model served over /v1/chat/completions with a bearer token.

    Presents the same two methods as OllamaClient, so nothing above this line
    knows which one it is talking to.

    Written for Cloudflare Workers AI, and equally valid against local Ollama's
    own /v1 endpoint — this is an interface, not a vendor.

    A spike measured @cf/meta/llama-4-scout-17b-16e-instruct at 33/33 routing
    over three passes, median 0.6s, against the real six-tool schema in both
    English and Tagalog. It also found that @cf/qwen/qwen3-30b-a3b-fp8 accepts
    the tools array and then returns the call as raw <tool_call> text instead
    of the structured field — which reads as "no tool call" here and would turn
    every question into a polite refusal. The model must return structured
    tool_calls, and a change of model needs the spike run again.
    """

    def __init__(self, base_url, model, token):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._token = token

    def _post(self, body):
        data = json.dumps(body).encode()
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions", data=data, method="POST",
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {self._token}"})
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                return json.loads(resp.read())
        except Exception as exc:                             # noqa: BLE001
            raise AIUnavailable(f"Model host unreachable: {exc}") from exc

    @staticmethod
    def _message(payload):
        choices = payload.get("choices") or []
        return (choices[0].get("message") or {}) if choices else {}

    def generate(self, prompt, system=""):
        body = {"model": self.model, "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt}]}
        return str(self._message(self._post(body)).get("content") or "").strip()

    def choose_tool(self, question, tool_payload, system):
        body = {"model": self.model, "tools": tool_payload, "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": question}]}
        message = self._message(self._post(body))
        calls = message.get("tool_calls") or []
        if not calls:
            # Prose, or a model that emitted <tool_call> text. Either way this
            # is not a tool call, and inventing one would be worse.
            return None, {}
        fn = calls[0].get("function") or {}
        args = fn.get("arguments")
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except ValueError:
                args = {}
        return fn.get("name"), (args or {})
```

Ensure `json`, `urllib.request` are imported at module scope (they already are, for `OllamaClient`).

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && ./.venv/Scripts/python.exe manage.py test assistant.tests.test_openai_client`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/assistant/services.py backend/assistant/tests/test_openai_client.py
git -c user.email=jreynoldcanedo@gmail.com commit --author="Reynold <jreynoldcanedo@gmail.com>" -m "Add a client for a model served over /v1/chat/completions

Presents the same two methods as OllamaClient, so nothing above it knows which
one it is talking to. Written for Cloudflare Workers AI and equally valid
against local Ollama's own /v1 endpoint — an interface, not a vendor.

Parsing is the part with teeth. A spike found that qwen3-30b accepts the tools
array and returns the call as raw <tool_call> text rather than in the
structured field; that reads as 'no tool call' here and would turn every
question into a polite refusal while the service looked healthy. Tests cover
structured calls, pre-parsed arguments, unparseable arguments and prose."
```

---

## Task 6: The guard, and choosing a client

The most important change in the plan. A hosted client creates the capability to send clinical text to an outside processor — the thing that removed the V2 layer.

**Files:**
- Modify: `backend/config/settings.py`
- Modify: `backend/assistant/services.py` (`get_ai_client`)
- Test: `backend/assistant/tests/test_hosted_guard.py`

**Interfaces:**
- Consumes: `OpenAICompatibleClient` from Task 5.
- Produces: settings `ASSISTANT_MODEL_URL`, `ASSISTANT_MODEL_TOKEN`, `ASSISTANT_MODEL_NAME`, `ASSISTANT_ALLOW_HOSTED_MODEL`; `get_ai_client()` returning `OpenAICompatibleClient` only when all four align.

- [ ] **Step 1: Write the failing test**

Create `backend/assistant/tests/test_hosted_guard.py`:

```python
"""A hosted model must be impossible to enable by accident.

The codebase says, deliberately: "There is deliberately only one provider. A
hosted API would mean sending clinical free text to an outside processor."
That rule is why the V2 AI layer was removed. These tests are the rule.
"""
from django.test import TestCase, override_settings

from assistant.models import AssistantSetting
from assistant.services import (NullClient, OllamaClient,
                                OpenAICompatibleClient, get_ai_client)

HOSTED = {
    "ASSISTANT_MODEL_URL": "https://api.example.invalid/v1",
    "ASSISTANT_MODEL_TOKEN": "a-token",
    "ASSISTANT_MODEL_NAME": "@cf/meta/llama-4-scout-17b-16e-instruct",
}


class HostedGuardTest(TestCase):
    def setUp(self):
        cfg = AssistantSetting.load()
        cfg.enabled = True
        cfg.save()

    def test_local_ollama_by_default(self):
        self.assertIsInstance(get_ai_client(), OllamaClient)

    @override_settings(ASSISTANT_ALLOW_HOSTED_MODEL=False, **HOSTED)
    def test_a_token_alone_is_not_consent(self):
        # Configuring credentials must not be enough. Someone pasting a key
        # into a dashboard has not decided that clinical text may leave.
        self.assertIsInstance(get_ai_client(), OllamaClient)

    @override_settings(ASSISTANT_ALLOW_HOSTED_MODEL=True, **HOSTED)
    def test_the_explicit_flag_enables_it(self):
        client = get_ai_client()
        self.assertIsInstance(client, OpenAICompatibleClient)
        self.assertEqual("@cf/meta/llama-4-scout-17b-16e-instruct", client.model)

    @override_settings(ASSISTANT_ALLOW_HOSTED_MODEL=True,
                       ASSISTANT_MODEL_URL="https://api.example.invalid/v1",
                       ASSISTANT_MODEL_TOKEN="", ASSISTANT_MODEL_NAME="m")
    def test_the_flag_without_a_token_falls_back_to_local(self):
        self.assertIsInstance(get_ai_client(), OllamaClient)

    @override_settings(ASSISTANT_ALLOW_HOSTED_MODEL=True, **HOSTED)
    def test_the_switch_still_wins(self):
        # The administrator's off switch outranks every environment variable.
        cfg = AssistantSetting.load()
        cfg.enabled = False
        cfg.save()
        self.assertIsInstance(get_ai_client(), NullClient)

    @override_settings(ASSISTANT_ALLOW_HOSTED_MODEL=True, **HOSTED)
    def test_the_database_url_cannot_redirect_a_hosted_model(self):
        # ollama_url is administrator-editable. On a public demo, anyone with
        # administrator credentials could otherwise repoint the model at a host
        # they control and capture every prompt.
        cfg = AssistantSetting.load()
        cfg.ollama_url = "http://attacker.invalid:11434"
        cfg.save()
        self.assertEqual("https://api.example.invalid/v1", get_ai_client().base_url)

    @override_settings(ASSISTANT_ALLOW_HOSTED_MODEL=True, **HOSTED)
    def test_it_announces_itself(self):
        with self.assertLogs("assistant.services", level="INFO") as logs:
            get_ai_client()
        joined = " ".join(logs.output)
        self.assertIn("llama-4-scout", joined)
        self.assertNotIn("a-token", joined)
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd backend && ./.venv/Scripts/python.exe manage.py test assistant.tests.test_hosted_guard`
Expected: FAIL — the settings do not exist.

- [ ] **Step 3: Add the settings**

Add to `backend/config/settings.py`, near the other assistant settings:

```python
# ---- Hosted model (optional; the demo deployment only) --------------------
# The assistant normally talks to a local Ollama and nothing leaves the
# machine. These four allow a hosted, OpenAI-compatible model instead — used
# by the public demo, whose children are fictional.
#
# ASSISTANT_ALLOW_HOSTED_MODEL is a separate, explicit acknowledgement on
# purpose. Credentials alone must not be enough: someone pasting a key into a
# dashboard has not decided that clinical free text may leave the building.
#
# The live blueprint sets none of these, so the live system cannot acquire a
# hosted provider by drift.
ASSISTANT_MODEL_URL = os.getenv("ASSISTANT_MODEL_URL", "").strip()
ASSISTANT_MODEL_TOKEN = os.getenv("ASSISTANT_MODEL_TOKEN", "").strip()
ASSISTANT_MODEL_NAME = os.getenv("ASSISTANT_MODEL_NAME", "").strip()
ASSISTANT_ALLOW_HOSTED_MODEL = (
    os.getenv("ASSISTANT_ALLOW_HOSTED_MODEL", "").strip().lower() == "true")
```

- [ ] **Step 4: Teach get_ai_client to choose**

Replace `get_ai_client()` in `backend/assistant/services.py`:

```python
def get_ai_client():
    """The one place that decides which model answers.

    Order matters. The administrator's off switch outranks everything; then a
    hosted model, but only with an explicit acknowledgement AND complete
    credentials; otherwise the local runtime, which is the default and the only
    one where nothing leaves the machine.

    The hosted branch deliberately ignores AssistantSetting.ollama_url. That
    field is administrator-editable, so on a public deployment anyone holding
    administrator credentials could otherwise repoint the model at a host they
    control and capture every prompt.
    """
    cfg = AssistantSetting.load()
    if not cfg.enabled:
        return NullClient()

    if (settings.ASSISTANT_ALLOW_HOSTED_MODEL
            and settings.ASSISTANT_MODEL_URL
            and settings.ASSISTANT_MODEL_TOKEN
            and settings.ASSISTANT_MODEL_NAME):
        # Said out loud, every time, so "which model answered this" is never a
        # guess. The token is never logged.
        logger.info("Assistant is using the HOSTED model %s at %s",
                    settings.ASSISTANT_MODEL_NAME, settings.ASSISTANT_MODEL_URL)
        return OpenAICompatibleClient(settings.ASSISTANT_MODEL_URL,
                                      settings.ASSISTANT_MODEL_NAME,
                                      settings.ASSISTANT_MODEL_TOKEN)

    return OllamaClient(cfg.ollama_url, cfg.model_name)
```

Ensure `from django.conf import settings` and a module-level
`logger = logging.getLogger(__name__)` exist in `services.py`.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd backend && ./.venv/Scripts/python.exe manage.py test assistant.tests.test_hosted_guard`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/config/settings.py backend/assistant/services.py backend/assistant/tests/test_hosted_guard.py
git -c user.email=jreynoldcanedo@gmail.com commit --author="Reynold <jreynoldcanedo@gmail.com>" -m "Make a hosted model impossible to enable by accident

The codebase says, deliberately, that there is only one provider because a
hosted API would mean sending clinical free text to an outside processor —
the rule that removed the V2 layer. This adds that capability back, so it adds
the lock at the same time.

Credentials alone are not consent: ASSISTANT_ALLOW_HOSTED_MODEL must be set
explicitly as well, and someone pasting a key into a dashboard has not decided
that clinical text may leave. The administrator's off switch still outranks
everything, and the hosted path ignores the administrator-editable ollama_url
so nobody with dashboard access can repoint the model at a host they control
and capture every prompt.

It says out loud at boot which model is answering, and never logs the token."
```

---

## Task 7: Rate limiting

**Files:**
- Modify: `backend/config/settings.py`
- Modify: `backend/assistant/views.py`
- Test: `backend/assistant/tests/test_throttling.py`

**Interfaces:**
- Consumes: nothing.
- Produces: throttle scopes `assistant_chat` and `assistant_draft`.

- [ ] **Step 1: Write the failing test**

Create `backend/assistant/tests/test_throttling.py`:

```python
"""One account must not be able to spend the day's allowance.

Every generation takes a process-wide lock, and the hosted allowance is 10,000
neurons a day. Without a ceiling, one signed-in visitor can hold the lock
continuously and exhaust the quota in minutes.
"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import override_settings
from rest_framework.test import APITestCase

from accounts.models import Role
from assistant import services
from assistant.models import AssistantSetting

User = get_user_model()
URL = "/api/assistant/ask/"


@override_settings(REST_FRAMEWORK={
    "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.ScopedRateThrottle"],
    "DEFAULT_THROTTLE_RATES": {"assistant_chat": "3/hour",
                               "assistant_draft": "3/hour"},
})
class ChatThrottleTest(APITestCase):
    def setUp(self):
        cache.clear()
        role = Role.objects.create(role_name=Role.PSYCHOLOGIST)
        self.psy = User.objects.create_user(
            email="p@racco1.gov.ph", username="p", password="pass1234", role=role)
        cfg = AssistantSetting.load()
        cfg.enabled = True
        cfg.save()
        self.client.force_authenticate(self.psy)

    def tearDown(self):
        cache.clear()

    def _ask(self):
        with patch.object(services.OllamaClient, "choose_tool",
                          return_value=("count_my_children", {"status": "active"})):
            return self.client.post(URL, {"question": "how many?"}, format="json")

    def test_allows_the_first_few(self):
        for _ in range(3):
            self.assertEqual(200, self._ask().status_code)

    def test_refuses_once_over_the_ceiling(self):
        for _ in range(3):
            self._ask()
        self.assertEqual(429, self._ask().status_code)

    def test_a_second_account_is_unaffected(self):
        # The ceiling is per account, so one abuser cannot silence everyone.
        for _ in range(4):
            self._ask()
        other = User.objects.create_user(
            email="q@racco1.gov.ph", username="q", password="pass1234",
            role=self.psy.role)
        self.client.force_authenticate(other)
        self.assertEqual(200, self._ask().status_code)
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd backend && ./.venv/Scripts/python.exe manage.py test assistant.tests.test_throttling`
Expected: FAIL — the fourth request returns 200, not 429.

- [ ] **Step 3: Configure the throttles**

Add to `REST_FRAMEWORK` in `backend/config/settings.py` (create the keys if absent):

```python
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.ScopedRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        # A demo visitor asking questions is fine; one holding the process-wide
        # generation lock all afternoon is not. The hosted allowance is 10,000
        # neurons a day across the whole account, so a per-account ceiling is
        # what keeps one person from spending everyone's.
        "assistant_chat": os.getenv("ASSISTANT_CHAT_RATE", "30/hour"),
        "assistant_draft": os.getenv("ASSISTANT_DRAFT_RATE", "20/hour"),
    },
```

- [ ] **Step 4: Attach the scopes**

In `backend/assistant/views.py`, add to `AssistantAskView`:

```python
    throttle_scope = "assistant_chat"
```

and to `PreSessionBriefView`, `PolishRemarkView`, `DocumentSummaryView` and
`CensusNarrativeView`:

```python
    throttle_scope = "assistant_draft"
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd backend && ./.venv/Scripts/python.exe manage.py test assistant`
Expected: PASS, including every existing assistant test.

- [ ] **Step 6: Commit**

```bash
git add backend/config/settings.py backend/assistant/views.py backend/assistant/tests/test_throttling.py
git -c user.email=jreynoldcanedo@gmail.com commit --author="Reynold <jreynoldcanedo@gmail.com>" -m "Stop one account spending the whole day's model allowance

There was no throttling anywhere in the application. Every generation takes a
process-wide lock and the hosted allowance is 10,000 neurons a day, so one
signed-in visitor could hold the lock continuously, make the assistant unusable
for everyone else, and exhaust the quota in minutes.

The ceiling is per account, so one abuser cannot silence the others, and both
rates are environment-tunable without a deploy."
```

---

## Task 8: A model reachability check

**Files:**
- Modify: `backend/assistant/views.py`, `backend/assistant/urls.py`
- Test: `backend/assistant/tests/test_model_health.py`

**Interfaces:**
- Consumes: `get_ai_client()` from Task 6.
- Produces: `GET /api/assistant/model-health/`, administrators only, returning `{"reachable": bool, "provider": "hosted"|"local"|"off", "model": str, "detail": str}`.

- [ ] **Step 1: Write the failing test**

Create `backend/assistant/tests/test_model_health.py`:

```python
"""Diagnosing "the chatbot is broken" without reading deployment logs."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from accounts.models import Role
from assistant import services
from assistant.models import AssistantSetting

User = get_user_model()
URL = "/api/assistant/model-health/"


class ModelHealthTest(APITestCase):
    def setUp(self):
        admin_role = Role.objects.create(role_name=Role.ADMINISTRATOR)
        psy_role = Role.objects.create(role_name=Role.PSYCHOLOGIST)
        self.admin = User.objects.create_user(
            email="a@racco1.gov.ph", username="a", password="pass1234",
            role=admin_role)
        self.psy = User.objects.create_user(
            email="p@racco1.gov.ph", username="p", password="pass1234",
            role=psy_role)
        cfg = AssistantSetting.load()
        cfg.enabled = True
        cfg.save()

    def test_reports_reachable_when_the_model_answers(self):
        self.client.force_authenticate(self.admin)
        with patch.object(services.OllamaClient, "generate", return_value="ok"):
            res = self.client.get(URL)
        self.assertEqual(200, res.status_code)
        self.assertTrue(res.data["reachable"])
        self.assertEqual("local", res.data["provider"])

    def test_reports_unreachable_rather_than_raising(self):
        self.client.force_authenticate(self.admin)
        with patch.object(services.OllamaClient, "generate",
                          side_effect=services.AIUnavailable("refused")):
            res = self.client.get(URL)
        self.assertEqual(200, res.status_code)
        self.assertFalse(res.data["reachable"])
        self.assertIn("refused", res.data["detail"])

    def test_reports_off_when_the_switch_is_off(self):
        cfg = AssistantSetting.load()
        cfg.enabled = False
        cfg.save()
        self.client.force_authenticate(self.admin)
        res = self.client.get(URL)
        self.assertEqual("off", res.data["provider"])
        self.assertFalse(res.data["reachable"])

    def test_a_psychologist_may_not_read_it(self):
        # It names the model host, which is deployment detail.
        self.client.force_authenticate(self.psy)
        self.assertEqual(403, self.client.get(URL).status_code)

    def test_anonymous_is_refused(self):
        self.assertIn(self.client.get(URL).status_code, (401, 403))
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd backend && ./.venv/Scripts/python.exe manage.py test assistant.tests.test_model_health`
Expected: FAIL — 404 on the URL.

- [ ] **Step 3: Write the view**

Add to `backend/assistant/views.py`:

```python
class ModelHealthView(AssistantBaseView):
    """Does the configured model answer? Administrators only.

    /healthz/ proves the database credential and nothing else. Without this,
    "the chatbot is broken" means reading deployment logs to find out whether
    the model host is down, the token is wrong, or the model was deprecated —
    and a hosted model can be retired underneath a running deployment.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if _role(request) != Role.ADMINISTRATOR:
            return Response({"detail": "Administrators only."},
                            status=status.HTTP_403_FORBIDDEN)

        cfg = AssistantSetting.load()
        if not cfg.enabled:
            return Response({"reachable": False, "provider": "off",
                             "model": "", "detail": "The assistant is switched off."})

        client = get_ai_client()
        hosted = isinstance(client, OpenAICompatibleClient)
        provider = "hosted" if hosted else "local"
        try:
            with services_lock():
                client.generate("Reply with the single word: ok", system="")
            return Response({"reachable": True, "provider": provider,
                             "model": client.model, "detail": ""})
        except AIUnavailable as exc:
            # Never a 5xx: the question was answered, and the answer is "no".
            return Response({"reachable": False, "provider": provider,
                             "model": getattr(client, "model", ""),
                             "detail": str(exc)[:300]})
```

Ensure `OpenAICompatibleClient` is imported in `views.py`.

- [ ] **Step 4: Add the route**

In `backend/assistant/urls.py`, beside the others:

```python
    path("assistant/model-health/", ModelHealthView.as_view(),
         name="assistant-model-health"),
```

Import `ModelHealthView` at the top.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd backend && ./.venv/Scripts/python.exe manage.py test assistant.tests.test_model_health`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/assistant/views.py backend/assistant/urls.py backend/assistant/tests/test_model_health.py
git -c user.email=jreynoldcanedo@gmail.com commit --author="Reynold <jreynoldcanedo@gmail.com>" -m "Report whether the configured model actually answers

/healthz/ proves the database credential and nothing else. Without this,
diagnosing 'the chatbot is broken' means reading deployment logs to work out
whether the host is down, the token is wrong, or the model was deprecated —
and a hosted model can be retired underneath a running deployment, which is
exactly what a spike hit when llama-3.1-8b returned 410.

Administrators only, because it names the model host. Unreachable is a 200 with
reachable=false: the question was answered, and the answer is no."
```

---

## Task 9: Measure the hosted model, and document it

**Files:**
- Modify: `backend/assistant/management/commands/ai_eval.py`
- Modify: `CLAUDE.md`
- Modify: `docs/CLOUD-DEPLOYMENT.md`

- [ ] **Step 1: Run the chat evaluation against the hosted model**

With `ASSISTANT_ALLOW_HOSTED_MODEL=true`, `ASSISTANT_MODEL_URL`,
`ASSISTANT_MODEL_TOKEN` and `ASSISTANT_MODEL_NAME` set in `backend/.env`:

```bash
cd backend && ./.venv/Scripts/python.exe manage.py ai_eval --feature chat --reps 3
```

Expected: routing comparable to the spike's 33/33. **Record the real number in
the commit message; do not reuse the spike's.** If any case fails, that is the
finding — report it rather than re-running until it passes.

- [ ] **Step 2: Add the hosted configuration to the deployment doc**

Append to the demo section of `docs/CLOUD-DEPLOYMENT.md`:

```markdown
### 6. Phase 2 — switch the chatbot on

In the Cloudflare dashboard: **AI → Workers AI → Use REST API** gives the
Account ID and a token with the right permissions prefilled.

On `nacc-v3-demo-api`, set four variables:

```
ASSISTANT_ALLOW_HOSTED_MODEL=true
ASSISTANT_MODEL_URL=https://api.cloudflare.com/client/v4/accounts/<ACCOUNT_ID>/ai/v1
ASSISTANT_MODEL_TOKEN=<the token>
ASSISTANT_MODEL_NAME=@cf/meta/llama-4-scout-17b-16e-instruct
```

All four are required. Credentials alone do nothing without the acknowledgement
flag, which is deliberate.

Then switch **Assistant enabled** back on in Settings, and confirm with
`GET /api/assistant/model-health/` as an administrator.

**The model name matters.** `@cf/qwen/qwen3-30b-a3b-fp8` accepts the tools
array and returns the call as raw `<tool_call>` text instead of the structured
field — the chatbot then refuses every question while looking healthy. If the
chosen model is ever retired (Cloudflare returns HTTP 410), the measured
fallback is `@cf/openai/gpt-oss-20b`.

**Only the chatbot runs on the hosted model.** Briefs, remark polish, document
summaries and the self-report model detector stay off: their numbers — 67%
Taglish drift, 28% detector miss — were measured on qwen2.5:3b and do not
transfer.
```

- [ ] **Step 3: Add a handbook section**

Add to `CLAUDE.md` after the chatbot section:

```markdown
## The demo deployment

Built 27 Aug 2026. Public, free, fictional children. Design in
`docs/superpowers/specs/2026-08-27-free-secure-web-deployment-design.md`.

- **It deploys from `local-ver`, never `origin`.** Services are named
  `nacc-v3-demo-*`; the live ones are `nacc-v3-api`/`nacc-v3-web` and are
  created from the other repository. Once the Blueprint is connected, a bare
  `git push` auto-deploys the demo.
- **The database is a Neon BRANCH, never `main`.** It exists so the demo
  inherits the real accounts while its writes — and the migrations this repo
  has that the live deployment does not — never reach production.
- **A hosted model needs `ASSISTANT_ALLOW_HOSTED_MODEL=true` as well as
  credentials.** Credentials alone are not consent. The live blueprint sets
  none of these, so the live system cannot acquire a hosted provider by drift.
- **The model must return structured `tool_calls`.**
  `@cf/qwen/qwen3-30b-a3b-fp8` returns them as raw `<tool_call>` text and the
  chatbot then refuses everything while looking healthy.
- **Cloudflare retires models** — `llama-3.1-8b` returns 410. Check
  `/api/assistant/model-health/` before assuming the code broke.
```

- [ ] **Step 4: Run the whole gate**

```bash
cd backend && ./.venv/Scripts/python.exe manage.py test
cd ../frontend && npm run lint && npm run build
```
Expected: all green. Update the test count in CLAUDE.md to the real number.

- [ ] **Step 5: Commit**

```bash
git add backend/assistant/management/commands/ai_eval.py CLAUDE.md docs/CLOUD-DEPLOYMENT.md
git -c user.email=jreynoldcanedo@gmail.com commit --author="Reynold <jreynoldcanedo@gmail.com>" -m "Measure the hosted model and write down what it needs

Records the configuration, the acknowledgement flag, and the two facts that
would otherwise cost a day: the model must return structured tool_calls, and
Cloudflare retires models underneath a running deployment.

States that only the chatbot runs hosted. The drafting features' numbers — 67%
Taglish drift, 28% detector miss — belong to qwen2.5:3b and do not transfer."
```

---

## Self-Review

**Spec coverage.** Two repositories → Task 1. Neon branch and demo children →
Tasks 2, 3, 4. Service rename → Task 1. CLAUDE.md correction → Tasks 1 and 9.
Empty R2 bucket → Task 4. Assistant off in Phase 1 → Task 4 step 5.
OpenAI-compatible client → Task 5. Hosted guard → Task 6. Rate limiting →
Task 7. Reachability check → Task 8. Model deprecation and the `<tool_call>`
trap → Tasks 5, 8, 9. "Only the chatbot is hosted" → Task 9.

**Known gap, deliberately left:** the chat pill stays visible when the
assistant is off, answering "unavailable". The spec records it as a rough edge
and no task fixes it — hiding it is a feature change, not a deployment concern.

**Type consistency.** `OpenAICompatibleClient(base_url, model, token)` is
defined in Task 5 and constructed in Task 6 with the three settings in that
order; `.model` and `.base_url` are read in Tasks 6 and 8. `get_ai_client()`
keeps its existing zero-argument signature, so `views.py` and `ai_eval` need no
change. The throttle scopes `assistant_chat` and `assistant_draft` are named
identically in Task 7's settings and views. `export_demo_data --output` writes
the file that `import_demo_data --fixture` reads.

**Placeholder scan:** none. Every step carries the actual content, and the two
steps that cannot be code — the dashboard work in Task 4 and the measurement in
Task 9 — carry exact commands and exact values instead.
