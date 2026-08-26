"""Detectors for scoring what the model actually wrote.

Pure functions over strings — no Django, no database, no model call — so they
are unit-testable on their own. That matters: the first attempt at a
hallucinated-name detector was swamped by markdown headings and looked like
evidence when it was noise. These have tests built from real captured output.

Used by `manage.py ai_eval`, which is a measuring instrument, not a test gate.
"""
import re
from collections import Counter

# A capitalised word is only interesting when the model set it *inside* a
# sentence. Every false positive in the first attempt — "Stands", "Has",
# "Changed", "Check" — sat at a line start or inside a **Title Case Heading:**.
# Requiring a lowercase word immediately before it removes that entire class,
# and keeps the real cases: "of Nakayuki's", "particularly Nakikisalamuha".
_MID_SENTENCE_CAP = re.compile(r"\b[a-z]+\s+([A-Z][a-z]{2,})\b")

_CAP_ANY = re.compile(r"\b([A-Z][a-z]{2,})\b")

# Capitalised in ordinary prose without being anybody's name.
_CALENDAR = {
    "january", "february", "march", "april", "may", "june", "july", "august",
    "september", "october", "november", "december",
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
}

# Tagalog function words and verb prefixes with no ordinary English meaning.
# "may" and "para" are deliberately excluded — both are common English, and a
# detector that flags them reports drift on clean output.
_TAGALOG_WORDS = {
    "ang", "ng", "mga", "sa", "hindi", "ako", "siya", "niya", "kanya",
    "kanila", "ito", "tungkol", "ngayon", "masyado", "kasi", "wala", "rin",
}
_TAGALOG_PREFIXES = ("nag-", "naka-", "naki-", "pag-", "nakiki")

# English reduplication reads as emphasis, not as a defect.
_REDUPLICATION_LINKS = {"and", "by", "after", "to", "upon", "for", "on"}


def invented_names(prompt, output):
    """Capitalised words the model introduced that the prompt never mentioned.

    A word already present in the prompt is cleared here even when the model
    has misused it — turning a Tagalog verb into a person, say. That misuse is
    a language-drift and readability problem, not an invented fact, and the
    other two detectors are what surface it.
    """
    known = {w.lower() for w in _CAP_ANY.findall(prompt)}
    known |= {w.lower() for w in re.findall(r"\b[a-z]{3,}\b", prompt)}

    found = []
    for word in _MID_SENTENCE_CAP.findall(output):
        low = word.lower()
        if low in known or low in _CALENDAR:
            continue
        if word not in found:
            found.append(word)
    return found


def repeated_lines(output):
    """Non-blank lines the model emitted more than once.

    Observed live: a brief that printed "**What Has Changed Recently:**" three
    times in one draft. Harmless to the record, but it reads as broken.
    """
    lines = [ln.strip() for ln in output.splitlines() if ln.strip()]
    return [line for line, n in Counter(lines).items() if n > 1]


def repeated_phrases(output, window=2, min_length=4):
    """Words the model repeated inside a single sentence.

    `repeated_lines` compares whole lines, so it could not see
    "Nakikisalamuha na Nakikisalamuha" — a defect that appeared in this
    module's own evaluation output and went unflagged.

    Only words of `min_length` or more count: "at the end of the day" repeats
    "the" two words apart and is ordinary English. The window is deliberately
    tight — a word legitimately reused later in a sentence ("settling in well
    and mixing well") is not a stutter.
    """
    # Repetition only counts inside one segment. A word appearing in two
    # adjacent headings — "**Percival's Case Brief** **Case Status:**" — is
    # document structure, not a stutter, and counting across that boundary
    # reported a false 13% defect rate across 60 runs.
    found = []
    for segment in re.split(r"[.!?;:]|\*\*|\n", output):
        _scan_segment(segment, window, min_length, found)
    return found


def _scan_segment(segment, window, min_length, found):
    words = re.findall(r"\b[\w'-]+\b", segment)
    for i, word in enumerate(words):
        if len(word) < min_length:
            continue
        ahead = words[i + 1:i + 1 + window]
        lowered = [w.lower() for w in ahead]
        if word.lower() not in lowered:
            continue
        # "more and more", "step by step", "side by side" are idiomatic English
        # emphasis, not stutters. The first version of this detector flagged all
        # of them and put a false 13% defect rate into an evaluation run. A
        # foreign linker ("na") is deliberately not on the list, so a genuine
        # repeat across one is still caught.
        if lowered.index(word.lower()) == 1 and ahead[0].lower() in _REDUPLICATION_LINKS:
            continue
        if word not in found:
            found.append(word)
    return found


def language_drift(output):
    """Tagalog markers in output that was asked for in English.

    Remark polish is instructed to return clear professional English. Against
    Taglish case notes it has returned Tagalog instead — once garbled badly
    enough to lose the original meaning.
    """
    low = output.lower()
    hits = [w for w in sorted(_TAGALOG_WORDS)
            if re.search(rf"\b{re.escape(w)}\b", low)]
    hits += [p for p in _TAGALOG_PREFIXES if p in low]
    return hits
