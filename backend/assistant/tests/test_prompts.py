from datetime import date

from django.test import TestCase

from assistant import prompts
from children.models import Child


class ChildAgeTest(TestCase):
    def test_unknown_when_no_birth_date(self):
        self.assertEqual(prompts.child_age(Child(fullname="A")), "unknown")

    def test_computed_from_birth_date(self):
        child = Child(fullname="A", birth_date=date(2015, 6, 1))
        age = prompts.child_age(child)
        self.assertTrue(age.isdigit(), f"expected a number, got {age!r}")


class BriefPromptTest(TestCase):
    def setUp(self):
        self.child = Child.objects.create(
            fullname="Maria Santos", birth_date=date(2015, 6, 1), gender="female")

    def test_includes_age_and_gender_so_the_model_need_not_guess(self):
        prompt = prompts.build_brief_prompt(self.child)
        self.assertIn("Age:", prompt)
        self.assertIn("Gender: female", prompt)

    def test_unspecified_gender_is_labelled_not_omitted(self):
        child = Child.objects.create(fullname="Ben", birth_date=None)
        prompt = prompts.build_brief_prompt(child)
        self.assertIn("Age: unknown", prompt)
        self.assertIn("Gender: unspecified", prompt)

    def test_forbids_inventing_details(self):
        self.assertIn("Do not state age, gender, or any other detail not given",
                      prompts.BRIEF_INSTRUCTIONS)

    def test_static_instructions_come_first_and_carry_no_case_data(self):
        """This is the prefix-cache guarantee: ~17s per call depends on it."""
        other = Child.objects.create(fullname="Juan Dela Cruz", gender="male")
        a = prompts.build_brief_prompt(self.child)
        b = prompts.build_brief_prompt(other)
        self.assertTrue(a.startswith(prompts.BRIEF_INSTRUCTIONS))
        self.assertTrue(b.startswith(prompts.BRIEF_INSTRUCTIONS))
        self.assertNotIn("Maria", prompts.BRIEF_INSTRUCTIONS)
        self.assertNotIn("Juan", prompts.BRIEF_INSTRUCTIONS)


class OtherPromptsTest(TestCase):
    def test_remark_prompt_puts_instructions_first(self):
        p = prompts.build_remark_prompt("kid came in late again")
        self.assertTrue(p.startswith(prompts.REMARK_INSTRUCTIONS))
        self.assertIn("kid came in late again", p)

    def test_summary_prompt_puts_instructions_first(self):
        p = prompts.build_summary_prompt("Some report text.", "report")
        self.assertTrue(p.startswith(prompts.SUMMARY_INSTRUCTIONS))
        self.assertIn("Some report text.", p)

    def test_census_prompt_forbids_calculating(self):
        p = prompts.build_census_prompt({"active_children": 40})
        self.assertTrue(p.startswith(prompts.CENSUS_INSTRUCTIONS))
        self.assertIn("active_children: 40", p)
        self.assertIn("Do not calculate", prompts.CENSUS_INSTRUCTIONS)
