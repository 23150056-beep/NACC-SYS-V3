"""Validator tests, written from what the model actually did.

The spike measured 91% functional accuracy on tool calls. Every remaining
failure was the model ignoring its own schema, and every case below is one that
was observed rather than imagined — a key with a colon in it, an enum value
that was not in the enum, an argument silently dropped.

The validator is a pure function over the model's output, so none of this needs
Django or a running Ollama.
"""
from django.test import SimpleTestCase

from assistant import tools


class NormalisesKeysTest(SimpleTestCase):
    def test_strips_punctuation_the_model_left_on_a_key(self):
        # Observed: {"when: ": "today"} — a naive args["when"] raises KeyError
        # and turns the whole turn into a 500.
        call = tools.validate("list_my_appointments", {"when: ": "today"})
        self.assertEqual(call.args, {"when": "today"})

    def test_strips_surrounding_whitespace(self):
        call = tools.validate("count_my_children", {"  status  ": "active"})
        self.assertEqual(call.args, {"status": "active"})


class CoercesEnumsTest(SimpleTestCase):
    def test_maps_a_tagalog_time_word_to_its_enum_value(self):
        # Observed four times: the model returned the Tagalog word itself
        # rather than the enum member. This alias is what takes 91% to 100%.
        call = tools.validate("list_my_appointments", {"when": "bukas"})
        self.assertEqual(call.args["when"], "tomorrow")

    def test_maps_ngayon_to_today(self):
        call = tools.validate("list_my_appointments", {"when": "ngayon"})
        self.assertEqual(call.args["when"], "today")

    def test_accepts_a_valid_enum_value_untouched(self):
        call = tools.validate("list_my_appointments", {"when": "this_week"})
        self.assertEqual(call.args["when"], "this_week")

    def test_is_case_insensitive(self):
        call = tools.validate("list_my_appointments", {"when": "Tomorrow"})
        self.assertEqual(call.args["when"], "tomorrow")

    def test_rejects_a_value_that_is_in_no_enum_and_has_no_alias(self):
        call = tools.validate("list_my_appointments", {"when": "someday"})
        self.assertFalse(call.ok)
        self.assertIn("when", call.error)


class RequiredArgumentsTest(SimpleTestCase):
    def test_rejects_a_missing_required_argument(self):
        # The model dropped optional free-text arguments on every single call,
        # so the ones that matter are required and their absence is fatal.
        call = tools.validate("search_children_by_concern", {})
        self.assertFalse(call.ok)
        self.assertIn("concern", call.error)

    def test_rejects_a_blank_required_argument(self):
        call = tools.validate("get_child_summary", {"name": "   "})
        self.assertFalse(call.ok)

    def test_accepts_a_tool_that_takes_no_arguments(self):
        call = tools.validate("list_care_gaps", {})
        self.assertTrue(call.ok)
        self.assertEqual(call.args, {})


class RejectsUnknownTest(SimpleTestCase):
    def test_rejects_a_tool_that_does_not_exist(self):
        call = tools.validate("delete_everything", {})
        self.assertFalse(call.ok)

    def test_drops_an_argument_the_schema_does_not_declare(self):
        # Scope must never come from the model. No tool declares an
        # "assigned_to_me" parameter, so an invented one is discarded rather
        # than reaching a queryset.
        call = tools.validate("count_my_children",
                              {"status": "active", "assigned_to_me": False})
        self.assertTrue(call.ok)
        self.assertNotIn("assigned_to_me", call.args)


class EchoTest(SimpleTestCase):
    """The echo line is the mitigation for a silently dropped filter: the user
    sees what the system understood before they see the answer."""

    def test_describes_the_call_in_the_users_words(self):
        call = tools.validate("search_children_by_concern",
                              {"concern": "school refusal"})
        self.assertIn("school refusal", call.echo)

    def test_a_tool_without_arguments_still_describes_itself(self):
        call = tools.validate("list_care_gaps", {})
        self.assertTrue(call.echo)


class SchemaShapeTest(SimpleTestCase):
    """Constraints the spike established, asserted so a later edit cannot
    quietly undo them."""

    def test_there_are_exactly_six_tools(self):
        # Four naive tools produced a misroute; six hardened ones scored 100%
        # on selection. A seventh needs its own evaluation run, not a hunch.
        self.assertEqual(6, len(tools.REGISTRY))

    def test_no_tool_declares_an_optional_free_text_parameter(self):
        # Measured: enum and required parameters survived every call; optional
        # free-text parameters were dropped on every call.
        for name, spec in tools.REGISTRY.items():
            for arg, meta in spec["schema"].items():
                with self.subTest(tool=name, arg=arg):
                    if not meta.get("required"):
                        self.assertIn("enum", meta)

    def test_no_tool_accepts_a_scope_argument(self):
        banned = {"assigned_to_me", "psychologist", "user", "child_id", "all"}
        for name, spec in tools.REGISTRY.items():
            with self.subTest(tool=name):
                self.assertFalse(banned & set(spec["schema"]))

    def test_every_tool_has_a_resolver(self):
        for name, spec in tools.REGISTRY.items():
            with self.subTest(tool=name):
                self.assertTrue(callable(spec["resolve"]))


class AnswerDirectlyTest(SimpleTestCase):
    """Measured: in one run of 28, the model called answer_directly with no
    `reason`. The reply is the same fixed copy regardless, so requiring it
    turned a correct routing decision into a failed turn."""

    def test_accepts_a_missing_reason(self):
        call = tools.validate("answer_directly", {})
        self.assertTrue(call.ok)

    def test_still_coerces_a_reason_when_given(self):
        call = tools.validate("answer_directly", {"reason": "general_knowledge"})
        self.assertEqual(call.args["reason"], "general_knowledge")
