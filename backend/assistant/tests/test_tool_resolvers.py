"""Resolver tests — the half of a tool that touches the database.

The model never sees any of this. A resolver takes a validated call and the
request, runs a real queryset under the caller's own scope, and returns a plain
dict the frontend renders. That is what makes a hallucinated child name
impossible: the names come out of the database, not out of a prompt.
"""
from datetime import datetime, time, timedelta

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from rest_framework.test import APIRequestFactory

from accounts.models import Role
from assistant import tools
from children.models import Child
from clinical.models import ProblemEntry, RemarkNote
from scheduling.models import Appointment

User = get_user_model()


class ResolverTestBase(TestCase):
    """Fixtures only — no tests. Two psychologists, so scope is testable."""

    def setUp(self):
        psy_role = Role.objects.create(role_name=Role.PSYCHOLOGIST)
        admin_role = Role.objects.create(role_name=Role.ADMINISTRATOR)
        self.psy = User.objects.create_user(
            email="p@racco1.gov.ph", username="p", password="pass1234", role=psy_role)
        self.other = User.objects.create_user(
            email="q@racco1.gov.ph", username="q", password="pass1234", role=psy_role)
        self.admin = User.objects.create_user(
            email="a@racco1.gov.ph", username="a", password="pass1234", role=admin_role)

        self.mine = Child.objects.create(
            fullname="Maria Santos", assigned_psychologist=self.psy)
        self.theirs = Child.objects.create(
            fullname="Juan Dela Cruz", assigned_psychologist=self.other)
        self.factory = APIRequestFactory()

    def _request(self, user):
        req = self.factory.get("/api/assistant/ask/")
        req.user = user
        return req

    def _resolve(self, user, tool, args):
        return tools.REGISTRY[tool]["resolve"](self._request(user), args)


class AppointmentsResolverTest(ResolverTestBase):
    def _appt(self, child, psychologist, days=0):
        # Anchored to mid-day on the target date, never now+N hours. A relative
        # offset crosses midnight when the suite runs late in the evening, and
        # the test then fails — or worse, passes — for a reason that has
        # nothing to do with the code.
        day = timezone.localdate() + timedelta(days=days)
        start = timezone.make_aware(
            datetime.combine(day, time(12, 0)),
            timezone.get_current_timezone())
        return Appointment.objects.create(
            child=child, psychologist=psychologist, start=start,
            status=Appointment.SCHEDULED)

    def test_returns_only_the_callers_own_appointments(self):
        self._appt(self.mine, self.psy)
        self._appt(self.theirs, self.other)
        out = self._resolve(self.psy, "list_my_appointments", {"when": "today"})
        names = [i["child"] for i in out["items"]]
        self.assertIn("Maria Santos", names)
        self.assertNotIn("Juan Dela Cruz", names)

    def test_tomorrow_excludes_todays_appointments(self):
        self._appt(self.mine, self.psy, days=0)
        out = self._resolve(self.psy, "list_my_appointments", {"when": "tomorrow"})
        self.assertEqual([], out["items"])

    def test_an_administrator_has_no_appointments_of_their_own(self):
        # Correct, not a bug: an administrator sees every child but holds no
        # sessions, so "who am I seeing" honestly returns nothing.
        self._appt(self.mine, self.psy)
        out = self._resolve(self.admin, "list_my_appointments", {"when": "today"})
        self.assertEqual([], out["items"])

    # --- periods, and the status that belongs to each ---------------------

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
        start, _ = tools.period_range("this_week")
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


class CountResolverTest(ResolverTestBase):
    def test_counts_only_children_the_caller_can_see(self):
        out = self._resolve(self.psy, "count_my_children", {"status": "active"})
        self.assertEqual(1, out["count"])

    def test_an_administrator_counts_every_child(self):
        out = self._resolve(self.admin, "count_my_children", {"status": "active"})
        self.assertEqual(2, out["count"])


class ConcernResolverTest(ResolverTestBase):
    """Fixtures use the agency's ACTUAL vocabulary, not invented text.

    The first version of these tests created a problem described as "School
    refusal since June" and passed. Live data records "School attendance
    difficulty" — so the test agreed with an assumption instead of checking it,
    and an exact-substring search that finds nothing shipped as green.
    """

    def setUp(self):
        super().setUp()
        ProblemEntry.objects.create(child=self.mine,
                                    description="School attendance difficulty",
                                    category="Educational")
        ProblemEntry.objects.create(child=self.mine,
                                    description="Sleep disturbance",
                                    category="Physical")

    def _search(self, term, user=None):
        return self._resolve(user or self.psy, "search_children_by_concern",
                             {"concern": term})

    def test_finds_the_agency_term_from_a_different_clinical_term(self):
        # The model says "school refusal"; the agency writes "School attendance
        # difficulty". A shared word is what connects them.
        out = self._search("school refusal")
        self.assertEqual(["Maria Santos"], [i["name"] for i in out["items"]])

    def test_finds_by_category(self):
        out = self._search("educational")
        self.assertEqual(["Maria Santos"], [i["name"] for i in out["items"]])

    def test_finds_by_a_single_word(self):
        out = self._search("sleep")
        self.assertEqual(["Maria Santos"], [i["name"] for i in out["items"]])

    def test_matches_a_plural_against_a_singular_record(self):
        # Live: "Any kids struggling with emotions?" found nothing while the
        # record read "Difficulty expressing emotion". icontains only looks one
        # way, so the plural the user types must be reduced too.
        ProblemEntry.objects.create(child=self.mine,
                                    description="Difficulty expressing emotion")
        out = self._search("emotions")
        self.assertEqual(["Maria Santos"], [i["name"] for i in out["items"]])

    def test_matches_an_ies_plural(self):
        ProblemEntry.objects.create(child=self.mine, description="Learning difficulty")
        out = self._search("difficulties")
        self.assertEqual(["Maria Santos"], [i["name"] for i in out["items"]])

    def test_ignores_short_words_so_everything_does_not_match(self):
        out = self._search("of the")
        self.assertEqual([], out["items"])

    def test_offers_the_recorded_vocabulary_when_nothing_matches(self):
        # A Tagalog phrase the model did not translate lands here. Showing what
        # IS recorded turns a dead end into something the user can act on.
        out = self._search("ayaw pumasok sa eskwela")
        self.assertEqual([], out["items"])
        self.assertIn("School attendance difficulty", out["available"])

    def test_the_vocabulary_offered_is_scoped_to_the_caller(self):
        ProblemEntry.objects.create(child=self.theirs,
                                    description="Adjustment to placement")
        out = self._search("nothing matches this")
        self.assertNotIn("Adjustment to placement", out["available"])

    def test_ignores_a_resolved_problem(self):
        ProblemEntry.objects.filter(child=self.mine).update(resolved=True)
        out = self._search("sleep")
        self.assertEqual([], out["items"])

    def test_does_not_reach_another_psychologists_child(self):
        ProblemEntry.objects.create(child=self.theirs, description="Sleep disturbance")
        out = self._search("sleep")
        self.assertEqual(["Maria Santos"], [i["name"] for i in out["items"]])

    def test_returns_names_not_problem_text(self):
        out = self._search("sleep")
        self.assertNotIn("Sleep disturbance", str(out["items"]))


class CareGapResolverTest(ResolverTestBase):
    """The demo database has no care gaps at all, so this tool has never
    returned a non-empty list against real data. Its shape is pinned here
    instead — the panel renders `message`, and a missing key would show as a
    blank line rather than an error."""

    def test_carries_the_human_message_not_the_slug(self):
        # An active child with no upcoming appointment is a gap by definition.
        out = self._resolve(self.psy, "list_care_gaps", {})
        self.assertTrue(out["items"], "expected the no-appointment gap")
        item = out["items"][0]
        self.assertEqual("Maria Santos", item["child"])
        self.assertTrue(item["message"])
        self.assertNotIn("_", item["message"])

    def test_is_scoped_to_the_caller(self):
        out = self._resolve(self.psy, "list_care_gaps", {})
        self.assertNotIn("Juan Dela Cruz", [i["child"] for i in out["items"]])


class SummaryResolverTest(ResolverTestBase):
    def test_finds_a_child_by_partial_name(self):
        out = self._resolve(self.psy, "get_child_summary", {"name": "maria"})
        self.assertEqual("Maria Santos", out["child"]["name"])

    def test_reports_no_match_rather_than_guessing(self):
        out = self._resolve(self.psy, "get_child_summary", {"name": "Nobody"})
        self.assertEqual("none", out["match"])

    def test_offers_the_choice_when_several_children_match(self):
        Child.objects.create(fullname="Maria Reyes", assigned_psychologist=self.psy)
        out = self._resolve(self.psy, "get_child_summary", {"name": "maria"})
        self.assertEqual("several", out["match"])
        self.assertEqual(2, len(out["items"]))

    def test_cannot_reach_another_psychologists_child(self):
        out = self._resolve(self.psy, "get_child_summary", {"name": "Juan"})
        self.assertEqual("none", out["match"])

    def test_respects_the_carry_history_control(self):
        # assignee_sees_history=False hides a previous psychologist's notes on
        # the screens. The chatbot must not become a way around that.
        Child.objects.filter(pk=self.mine.pk).update(assignee_sees_history=False)
        RemarkNote.objects.create(child=self.mine, author=self.other, text="Earlier note")
        RemarkNote.objects.create(child=self.mine, author=self.psy, text="My own note")
        out = self._resolve(self.psy, "get_child_summary", {"name": "maria"})
        texts = [r["text"] for r in out["remarks"]]
        self.assertIn("My own note", texts)
        self.assertNotIn("Earlier note", texts)

    def test_shows_every_remark_when_history_is_carried(self):
        RemarkNote.objects.create(child=self.mine, author=self.other, text="Earlier note")
        out = self._resolve(self.psy, "get_child_summary", {"name": "maria"})
        self.assertIn("Earlier note", [r["text"] for r in out["remarks"]])


class DirectResolverTest(ResolverTestBase):
    def test_returns_fixed_copy_never_model_prose(self):
        out = self._resolve(self.psy, "answer_directly", {"reason": "general_knowledge"})
        self.assertIn("schedule", out["text"].lower())

    def test_works_without_a_reason(self):
        out = self._resolve(self.psy, "answer_directly", {})
        self.assertTrue(out["text"])


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
