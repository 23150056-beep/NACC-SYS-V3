"""Scoring for the NACC-SAMD-GF-000 self-assessment (see checklist.py for the
source citation). Formula per the official tool (~lines 330-340 of the source
doc): Actual Score = count(Yes) + count(N/A); Percentage = Total Actual Score
divided by Total Indicators x 100. Certification bands: 75-100% Full
Certification, 60-74% Conditional Approval, 59% or below Non-Certification.
"""
from samd.checklist import CHECKLIST

BANDS = [
    {"min": 75, "max": 100, "label": "Full Certification"},
    {"min": 60, "max": 74, "label": "Conditional Approval"},
    {"min": 0, "max": 59, "label": "Non-Certification"},
]


def band_for_pct(pct):
    for band in BANDS:
        if band["min"] <= pct <= band["max"]:
            return band["label"]
    return BANDS[-1]["label"]


def compute_scores(assessment):
    """Per-KRA and overall score breakdown for one SamdAssessment instance."""
    responses = {r.item_key: r.compliance for r in assessment.responses.all()}

    kra_scores = []
    overall = {"total": 0, "yes": 0, "not": 0, "na": 0, "unanswered": 0}
    for kra in CHECKLIST:
        items = kra["items"]
        total = len(items)
        yes = not_count = na = 0
        for item in items:
            compliance = responses.get(item["key"], "")
            if compliance == "yes":
                yes += 1
            elif compliance == "not":
                not_count += 1
            elif compliance == "na":
                na += 1
        unanswered = total - yes - not_count - na
        actual_score = yes + na
        pct = round(actual_score / total * 100, 1) if total else 0.0
        kra_scores.append({
            "key": kra["key"],
            "title": kra["title"],
            "total": total,
            "yes": yes,
            "not": not_count,
            "na": na,
            "unanswered": unanswered,
            "actual_score": actual_score,
            "pct": pct,
        })
        overall["total"] += total
        overall["yes"] += yes
        overall["not"] += not_count
        overall["na"] += na
        overall["unanswered"] += unanswered

    overall["actual_score"] = overall["yes"] + overall["na"]
    overall["pct"] = round(overall["actual_score"] / overall["total"] * 100, 1) if overall["total"] else 0.0
    overall["band"] = band_for_pct(overall["pct"])

    return {"kras": kra_scores, "overall": overall}
