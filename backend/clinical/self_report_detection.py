"""Distress detection over a child's self-report.

Deterministic, sub-millisecond, no runtime dependency. This is the floor: if
Ollama is down, swapped, or drifting, flagging continues unchanged. A
child-safety signal must not depend on a 3B model running on a laptop.

Detection reads the (question, answer) PAIR, never the answer alone. In the
live data, 62 of 122 reports answer "Who do you talk to when you are sad?"
with "Nobody" or "Ako lang" — the largest signal present, and invisible to
anything reading answer text on its own.

The list is assumed incomplete. It is supplemented by the model detector, and
unflagged reports stay visible on the child's page, so a miss is unhighlighted
rather than hidden. Every flag records the phrase that fired, which is how the
list gets tuned from what children actually write.
"""
import re

# Phrases in the three languages the children actually write. Adding one is a
# one-line change, which is the point.
DISTRESS_PHRASES = {
    "tl": (
        "umiiyak", "iyak", "umiyak", "gusto ko na umuwi", "gusto ko umuwi",
        "hindi ko masabi", "ayaw ko na", "ayaw ko dito", "ayaw ko na dito",
        "takot", "natatakot", "masakit", "nasasaktan", "walang kausap",
        "wala akong makausap", "wala akong kaibigan", "nag-iisa",
        "malungkot", "lungkot", "gusto ko na lang matulog", "binubugbog",
        "sinasaktan", "baka magalit", "galit sila",
    ),
    # NOT REVIEWED BY AN ILOCANO SPEAKER — see LEXICON_REVIEWED below. These
    # were seeded from phrases observed in the database plus a small number of
    # high-confidence terms.
    "ilo": (
        "mabutbuteng", "agbutbuteng", "agsangsangit", "agsangit",
        "adda problema", "adda parikut", "adda met bassit nga problema",
        "kayat ko nga agawid", "maladingit", "ladingit",
    ),
    "en": (
        "i feel alone", "feel alone", "nobody listens", "no one listens",
        "i am scared", "i'm scared", "scared", "afraid",
        "cannot sleep", "can't sleep", "cry", "crying", "cries",
        "want to go home", "hurts", "hurting", "hit me", "nobody helps",
    ),
}

# Which language lists have been read by a speaker of that language. An
# invented entry is worse than a missing one because it looks authoritative.
LEXICON_REVIEWED = {"tl": True, "ilo": False, "en": True}

# The isolation rule. "Nobody" is an unremarkable word; against this question
# it is the single largest distress signal in the dataset.
ISOLATION_QUESTION_HINTS = ("talk to when you are sad", "talk to when sad",
                            "kausap", "kinakausap")
ISOLATION_ANSWERS = ("nobody", "no one", "none", "no body", "ako lang",
                     "awan", "sarili ko", "myself", "just me", "sarilik")


def _norm(text):
    return " ".join(str(text or "").lower().split())


def _contains_word(haystack, needle):
    """Word-boundary match, so a phrase never fires inside a longer word."""
    return re.search(rf"(?<!\w){re.escape(needle)}(?!\w)", haystack) is not None


def _is_isolation_question(question):
    q = _norm(question)
    return any(hint in q for hint in ISOLATION_QUESTION_HINTS)


def detect_concerns(question, answer):
    """Return the matches for one (question, answer) pair.

    Each match is {"phrase": <what fired>, "rule": "phrase" | "isolation"}.

    An empty list is never a claim that the child is fine — only that this
    list did not recognise anything. That distinction is why unflagged reports
    stay visible on her page.
    """
    text = _norm(answer)
    if not text:
        return []

    hits = []

    if _is_isolation_question(question):
        for candidate in ISOLATION_ANSWERS:
            if _contains_word(text, candidate):
                hits.append({"phrase": candidate, "rule": "isolation"})
                break

    for phrases in DISTRESS_PHRASES.values():
        for phrase in phrases:
            if _contains_word(text, phrase):
                hits.append({"phrase": phrase, "rule": "phrase"})

    seen, unique = set(), []
    for hit in hits:
        if hit["phrase"] not in seen:
            seen.add(hit["phrase"])
            unique.append(hit)
    return unique
