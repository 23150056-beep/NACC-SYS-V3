"""The chat endpoint: question in, a validated tool call and its result out.

Every test patches the client. The model's only job is choosing a tool, so
these assert the wiring around that choice — the gate, the length cap, the
validator, the audit row, and the fact that a rejected call never reaches a
queryset.
"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from accounts.models import Role
from assistant import services
from assistant.models import AssistantJob, AssistantSetting
from children.models import Child

User = get_user_model()
URL = "/api/assistant/ask/"


class AskTestBase(APITestCase):
    def setUp(self):
        psy_role = Role.objects.create(role_name=Role.PSYCHOLOGIST)
        self.psy = User.objects.create_user(
            email="p@racco1.gov.ph", username="p", password="pass1234", role=psy_role)
        self.other = User.objects.create_user(
            email="q@racco1.gov.ph", username="q", password="pass1234", role=psy_role)
        self.mine = Child.objects.create(
            fullname="Maria Santos", assigned_psychologist=self.psy)
        self.theirs = Child.objects.create(
            fullname="Juan Dela Cruz", assigned_psychologist=self.other)
        cfg = AssistantSetting.load()
        cfg.enabled = True
        cfg.save()
        self.client.force_authenticate(self.psy)

    def _ask(self, question, tool, args):
        with patch.object(services.OllamaClient, "choose_tool",
                          return_value=(tool, args)):
            return self.client.post(URL, {"question": question}, format="json")


class AskHappyPathTest(AskTestBase):
    def test_returns_the_tool_the_echo_and_the_result(self):
        res = self._ask("how many children do I have?",
                        "count_my_children", {"status": "active"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["tool"], "count_my_children")
        self.assertIn("active", res.data["echo"])
        self.assertEqual(res.data["result"]["count"], 1)

    def test_audits_the_question_and_the_call(self):
        self._ask("ilan ang mga bata ko?", "count_my_children", {"status": "aktibo"})
        job = AssistantJob.objects.get()
        self.assertEqual(job.job_type, "chat")
        self.assertIn("ilan ang mga bata", job.input_ref)
        self.assertIn("count_my_children", job.output_text)
        self.assertEqual(job.created_by, self.psy)

    def test_a_tagalog_enum_value_is_aliased_before_it_reaches_the_queryset(self):
        res = self._ask("ilan ang mga bata ko?",
                        "count_my_children", {"status": "aktibo"})
        self.assertEqual(res.data["result"]["status"], "active")

    def test_scope_comes_from_the_caller_not_the_model(self):
        # The model inventing an "assigned_to_me" argument must not widen the
        # caller's view — the argument is discarded and the queryset is scoped
        # by request.user regardless.
        res = self._ask("how many children?", "count_my_children",
                        {"status": "active", "assigned_to_me": False})
        self.assertEqual(res.data["result"]["count"], 1)


class AskRejectionTest(AskTestBase):
    def test_an_unknown_tool_is_explained_not_guessed(self):
        res = self._ask("drop the database", "delete_everything", {})
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.data["ok"])
        self.assertIn("didn't follow", res.data["message"])

    def test_a_missing_required_argument_is_explained(self):
        res = self._ask("find children", "search_children_by_concern", {})
        self.assertFalse(res.data["ok"])

    def test_a_rejected_call_never_runs_a_query(self):
        res = self._ask("find children", "search_children_by_concern", {})
        self.assertNotIn("result", res.data)

    def test_a_rejected_call_is_audited_as_a_failure(self):
        self._ask("drop the database", "delete_everything", {})
        self.assertFalse(AssistantJob.objects.get().ok)

    def test_prose_instead_of_a_tool_call_becomes_a_direct_answer(self):
        res = self._ask("what is depression?", None, {})
        self.assertEqual(res.data["tool"], "answer_directly")
        self.assertIn("schedule", res.data["result"]["text"].lower())


class AskGuardTest(AskTestBase):
    def test_503_when_the_assistant_is_off(self):
        cfg = AssistantSetting.load()
        cfg.enabled = False
        cfg.save()
        res = self.client.post(URL, {"question": "hello"}, format="json")
        self.assertEqual(res.status_code, 503)

    def test_400_when_the_question_is_too_long(self):
        res = self.client.post(URL, {"question": "x" * 151}, format="json")
        self.assertEqual(res.status_code, 400)

    def test_400_when_the_question_is_blank(self):
        res = self.client.post(URL, {"question": "   "}, format="json")
        self.assertEqual(res.status_code, 400)

    def test_400_when_the_question_is_not_a_string(self):
        res = self.client.post(URL, {"question": 5}, format="json")
        self.assertEqual(res.status_code, 400)

    def test_anonymous_is_refused(self):
        self.client.force_authenticate(None)
        res = self.client.post(URL, {"question": "hello"}, format="json")
        self.assertIn(res.status_code, (401, 403))

    def test_503_when_the_runtime_is_unreachable(self):
        err = services.AIUnavailable("Local AI runtime unreachable: refused")
        with patch.object(services.OllamaClient, "choose_tool", side_effect=err):
            res = self.client.post(URL, {"question": "hello"}, format="json")
        self.assertEqual(res.status_code, 503)
        self.assertFalse(AssistantJob.objects.get().ok)


class AskScopeTest(AskTestBase):
    def test_cannot_summarise_another_psychologists_child(self):
        res = self._ask("tell me about Juan", "get_child_summary", {"name": "Juan"})
        self.assertEqual(res.data["result"]["match"], "none")


class AskMisrouteTest(AskTestBase):
    """Seen in the browser: "how many psychologist are in the system?" came
    back "40 active children" — a confident, wrong number."""

    def test_a_staff_question_does_not_return_a_child_count(self):
        res = self._ask("how many psychologist are in the system?",
                        "count_my_children", {"status": "active"})
        self.assertEqual("answer_directly", res.data["tool"])
        self.assertNotIn("count", res.data["result"])

    def test_it_says_what_it_can_do_instead(self):
        res = self._ask("How many staff are in the system?",
                        "count_my_children", {"status": "active"})
        self.assertIn("children", res.data["result"]["text"].lower())

    def test_a_real_child_count_still_answers(self):
        res = self._ask("How many children am I handling?",
                        "count_my_children", {"status": "active"})
        self.assertEqual("count_my_children", res.data["tool"])
        self.assertEqual(1, res.data["result"]["count"])
