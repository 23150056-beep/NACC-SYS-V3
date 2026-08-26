"""Detector tests over the (question, answer) pair.

Every distress and calm fixture below is a string that appears in the live
local database, copied rather than paraphrased. On 26 Aug a search feature
shipped green because its test invented text that agreed with the assumption
being tested; these strings were taken from the data instead.

The two RobustnessTest inputs are synthetic on purpose — they exercise the
matcher itself (word boundaries, empty input), not the vocabulary.
"""
from django.test import SimpleTestCase

from clinical.self_report_detection import detect_concerns

FEELING = "How are you feeling this week?"
WORRY = "Is there anything worrying you?"
ISOLATION = "Who do you talk to when you are sad?"


class DistressTest(SimpleTestCase):
    def test_flags_crying_and_wanting_to_go_home(self):
        self.assertTrue(detect_concerns(
            FEELING, "Gusto ko na umuwi. Lagi akong umiiyak sa gabi."))

    def test_flags_being_unable_to_speak_and_somatic_pain(self):
        self.assertTrue(detect_concerns(
            WORRY, "Hindi ko masabi kasi baka magalit sila. Masakit ang dibdib ko."))

    def test_flags_feeling_alone_and_wanting_to_sleep(self):
        self.assertTrue(detect_concerns(
            FEELING, "I feel alone. Ayaw ko na dito, gusto ko na lang matulog."))

    def test_flags_nobody_listening(self):
        self.assertTrue(detect_concerns(
            WORRY, "Nobody listens to me here. Wala akong makausap."))

    def test_reports_which_phrase_fired(self):
        hits = detect_concerns(FEELING, "Lagi akong umiiyak sa gabi.")
        self.assertIn("umiiyak", [h["phrase"] for h in hits])


class IlocanoTest(SimpleTestCase):
    """The children are in Ilocos. A Tagalog-only list passes both of these."""

    def test_flags_mabutbuteng(self):
        self.assertTrue(detect_concerns(
            FEELING, "Mabutbuteng. I am scared but I don't tell them."))

    def test_flags_adda_problema(self):
        self.assertTrue(detect_concerns(
            WORRY, "Adda met bassit nga problema but I don't want to say."))

    def test_does_not_flag_the_calm_ilocano_line(self):
        # "Naimbag met" — it is good. The Ilocano control.
        self.assertEqual([], detect_concerns(
            FEELING, "Naimbag met. I can sleep at night now."))


class CalmTest(SimpleTestCase):
    """Without these a lexicon scores perfectly by flagging everything."""

    def test_does_not_flag_feeling_safe(self):
        self.assertEqual([], detect_concerns(
            FEELING, "I feel safe. Ang bait ng nag-aalaga sa akin."))

    def test_does_not_flag_liking_the_food(self):
        self.assertEqual([], detect_concerns(
            FEELING, "Okay lang. I like the food and my bed."))

    def test_does_not_flag_having_a_friend(self):
        self.assertEqual([], detect_concerns(
            FEELING, "Masaya naman ako dito. May kaibigan na ako."))

    def test_does_not_flag_missing_a_sibling_with_kind_carers(self):
        self.assertEqual([], detect_concerns(
            FEELING, "I miss my sister. But the people here are kind."))


class IsolationQuestionTest(SimpleTestCase):
    """62 of 122 reports answer the isolation question with a word meaning
    'no one'. Those words are unremarkable anywhere else, which is exactly why
    detection reads the question and not just the answer."""

    def test_nobody_flags_against_the_isolation_question(self):
        hits = detect_concerns(ISOLATION, "Nobody")
        self.assertEqual("isolation", hits[0]["rule"])

    def test_ako_lang_flags_against_the_isolation_question(self):
        self.assertTrue(detect_concerns(ISOLATION, "Ako lang"))

    def test_nobody_does_not_flag_against_another_question(self):
        self.assertEqual([], detect_concerns(FEELING, "Nobody"))

    def test_naming_a_person_does_not_flag(self):
        self.assertEqual([], detect_concerns(ISOLATION, "My sister"))
        self.assertEqual([], detect_concerns(ISOLATION, "Ate sa bahay"))

    def test_an_unknown_question_falls_back_to_phrases(self):
        # A template can be edited. An unrecognised question must still detect
        # phrases rather than failing shut.
        self.assertTrue(detect_concerns(
            "Some new question?", "Lagi akong umiiyak sa gabi."))


class RobustnessTest(SimpleTestCase):
    def test_is_case_insensitive(self):
        self.assertTrue(detect_concerns(ISOLATION, "NOBODY"))

    def test_a_blank_answer_flags_nothing(self):
        self.assertEqual([], detect_concerns(FEELING, ""))
        self.assertEqual([], detect_concerns(FEELING, None))

    def test_a_missing_question_still_flags_the_answer(self):
        # Fails open, deliberately. Only the isolation RULE needs the question;
        # a distress phrase is distress whether or not we know what was asked.
        # Losing a flag because a question went missing would be the worst
        # possible way to fail.
        self.assertTrue(detect_concerns(None, "Lagi akong umiiyak"))

    def test_does_not_match_a_phrase_inside_an_unrelated_word(self):
        # Synthetic: exercises the word-boundary matcher, not the vocabulary.
        self.assertEqual([], detect_concerns(FEELING, "Walang problema, masaya ako."))
