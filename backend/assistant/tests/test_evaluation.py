"""Detector tests, built from strings the model actually produced.

Every fixture here is a real output captured while evaluating the shipped
drafting features against real remarks. A detector is only worth having if it
flags what we saw go wrong and stays quiet on what was fine, so both directions
are asserted.
"""
from django.test import SimpleTestCase

from assistant import evaluation


class InventedNamesTest(SimpleTestCase):
    """A capitalised word the model introduced mid-sentence is the signal that
    matters clinically: it reads as a person."""

    PROMPT = ("FACTS:\nFirst name: Yolanda\nAge: 9\nGender: female\n"
              "Recent remarks (newest first):\n"
              "- 2026-08-08: Settling in well. Nakikisalamuha na sa ibang bata "
              "during recreation.\n")

    def test_flags_a_name_the_model_invented(self):
        out = "This is a positive sign and part of Nakayuki's development."
        self.assertIn("Nakayuki", evaluation.invented_names(self.PROMPT, out))

    def test_flags_a_tagalog_verb_read_as_a_person(self):
        out = "She is settling well with peers, particularly Nakikisalamuha."
        # The word IS in the prompt, but as prose the model has turned it into
        # a person. Presence in the prompt is what clears it — so this must NOT
        # flag, and the repetition/drift detectors are what catch this case.
        self.assertEqual([], evaluation.invented_names(self.PROMPT, out))

    def test_does_not_flag_a_markdown_heading(self):
        out = "**What Has Changed Recently:**\nShe attended every session."
        self.assertEqual([], evaluation.invented_names(self.PROMPT, out))

    def test_does_not_flag_a_sentence_opener(self):
        out = "Continued positive engagement.\nAdditionally, her mood improved."
        self.assertEqual([], evaluation.invented_names(self.PROMPT, out))

    def test_does_not_flag_a_bulleted_opener(self):
        out = "- Observe if she can maintain focus during longer sessions."
        self.assertEqual([], evaluation.invented_names(self.PROMPT, out))

    def test_does_not_flag_the_childs_own_name(self):
        out = "During this session, check whether Yolanda seems withdrawn."
        self.assertEqual([], evaluation.invented_names(self.PROMPT, out))

    def test_does_not_flag_a_month_or_weekday(self):
        out = "She refused to join on August 22 and again on Friday."
        self.assertEqual([], evaluation.invented_names(self.PROMPT, out))

    def test_flags_only_the_novel_word_when_mixed(self):
        out = "Yolanda spoke about Marisol during the session."
        self.assertEqual(["Marisol"], evaluation.invented_names(self.PROMPT, out))


class RepeatedLinesTest(SimpleTestCase):
    def test_flags_a_heading_emitted_three_times(self):
        out = ("**Where the Case Stands:**\nShe is engaged.\n"
               "**What Has Changed Recently:**\n"
               "**What Has Changed Recently:**\n"
               "**What Has Changed Recently:**\n")
        self.assertIn("**What Has Changed Recently:**",
                      evaluation.repeated_lines(out))

    def test_ignores_blank_lines(self):
        self.assertEqual([], evaluation.repeated_lines("One.\n\n\nTwo.\n\n"))

    def test_clean_output_reports_nothing(self):
        out = "Where the case stands: engaged.\nWhat changed: nothing.\n"
        self.assertEqual([], evaluation.repeated_lines(out))


class LanguageDriftTest(SimpleTestCase):
    """Remark polish is instructed to return clear professional English. It
    returned Tagalog instead, and once returned garbled Tagalog that lost the
    original meaning."""

    def test_flags_the_garbled_tagalog_polish(self):
        out = ("Nakikisalamuha ng anak ng mother dito sa mga pagkakaiba ng "
               "bata sa recreation time.")
        self.assertTrue(evaluation.language_drift(out))

    def test_flags_untranslated_input_echoed_back(self):
        out = ("NOTE: Nag-aalala pa rin tungkol sa school. Hindi masyado "
               "nagsasalita ngayon.")
        self.assertTrue(evaluation.language_drift(out))

    def test_clean_english_does_not_drift(self):
        out = "Settling in well. Mixing with the other children during recreation."
        self.assertEqual([], evaluation.language_drift(out))

    def test_english_words_are_not_mistaken_for_tagalog(self):
        # "may" and "para" are deliberately absent from the marker set because
        # they are ordinary English; a detector that flags them is useless.
        out = "She may attend on Friday. The parameters of the plan are set."
        self.assertEqual([], evaluation.language_drift(out))


class RepeatedPhrasesTest(SimpleTestCase):
    """`repeated_lines` works on whole lines, so it missed a real defect sitting
    in its own evaluation output: "Nakikisalamuha na Nakikisalamuha" — the same
    word twice in one sentence. Line-level checks cannot see inside a line.
    """

    def test_flags_a_word_repeated_within_a_sentence(self):
        out = "Nakikisalamuha na Nakikisalamuha sa ibang bata dito sa recreation."
        self.assertIn("Nakikisalamuha", evaluation.repeated_phrases(out))

    def test_flags_an_immediate_stutter(self):
        self.assertIn("child", evaluation.repeated_phrases("The child child is well."))

    def test_ignores_short_function_words(self):
        # "the end of the day" repeats "the" close together and is ordinary.
        self.assertEqual([], evaluation.repeated_phrases("At the end of the day."))

    def test_ignores_a_word_reused_further_along(self):
        out = "Settling in well and mixing well with the other children."
        self.assertEqual([], evaluation.repeated_phrases(out))

    def test_clean_output_reports_nothing(self):
        out = "The child attended the session and completed the drawing task."
        self.assertEqual([], evaluation.repeated_phrases(out))

    def test_ignores_ordinary_english_reduplication(self):
        # "more and more", "step by step" and friends are idiomatic, not
        # stutters. The first version of this detector flagged all of them,
        # which put a false 13% defect rate into an evaluation run.
        for phrase in ("She is more and more engaged.",
                       "Progress has been step by step.",
                       "She opened up little by little.",
                       "They sat side by side.",
                       "He asked over and over about the visit."):
            with self.subTest(phrase=phrase):
                self.assertEqual([], evaluation.repeated_phrases(phrase))

    def test_still_flags_a_repeat_across_a_foreign_connector(self):
        # "na" is a Tagalog linker, not an English reduplication connector.
        out = "Nakikisalamuha na Nakikisalamuha sa ibang bata."
        self.assertIn("Nakikisalamuha", evaluation.repeated_phrases(out))
