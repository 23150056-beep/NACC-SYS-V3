"""Prompt templates. Minimum-necessary data only (RA 10173): first name and
clinical context, never full identity dumps."""

SYSTEM = ("You are a documentation assistant for a licensed child psychologist "
          "at a Philippine child-care agency. Be concise, professional, and "
          "clinical. Never diagnose. Never invent facts not in the input.")

BRIEF = """Write a pre-session brief (max 150 words) for the psychologist who
is about to see this child. Summarize current status, recent findings, open
problems, and one or two suggested focus points for today's session.

Child (first name): {first_name}
Age: {age}
Sex/gender: {gender}
Case type: {case_type}
Latest pre-assessment: {pre_assessment}
Latest result entry: {latest_result}
Open problems: {problems}
Recent remarks:
{remarks}
Child's own answers to the agency self-report opinionnaire (verbatim; note any
recurring emotional keywords or distress indicators):
{opinionnaire}

Use only the facts provided above. Do not state age, gender, or any other detail
not given. Refer to the child by first name only.
"""

DOC_INTELLIGENCE = """From the psychologist's own report text below, draft:
1. Key findings (3-5 bullet points)
2. Recommendations (2-4 bullet points)
3. Classification in the author's words (one line)

Only use information present in the text.

REPORT TEXT:
{text}
"""

REMARK_POLISH = """Rewrite this shorthand remark as one short paragraph of
clean clinical prose. Keep every fact; add none. Keep the author's meaning.

REMARK: {text}
"""

CENSUS_NARRATIVE = """Write a short narrative paragraph (max 120 words) for a
monthly agency report, summarizing these caseload statistics in plain,
professional English:

{stats}
"""

CASE_REFERRAL = """From the social worker's case referral text below, draft:
1. Background and family/social context (3-5 bullet points)
2. Presenting concerns (2-4 bullet points)
3. Recommendations noted by the author (1-3 bullet points)

Only use information present in the text.

CASE REFERRAL TEXT:
{text}
"""
