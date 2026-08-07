"""Seed the official agency-authored forms (idempotent).

Content transcribed from the real documents in docs/agency-forms/
(agency-authored — inside the copyright boundary; see the 2026-07-14 spec).
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from clinical.models import AgencyFormTemplate


def _sec(label):
    return {"label": label, "field_type": "section", "options": []}


def _q(label):
    return {"label": label, "field_type": "long_text", "options": []}


CONSENT_TITLE = "Informed Consent for Psychological Evaluation (Adoption)"

# Verbatim body: copied from between the <!-- BODY BEGIN --> and
# <!-- BODY END --> markers in
# docs/agency-forms/informed-consent-adoption-extracted.md
CONSENT_BODY = """This Informed Consent Form is executed by the undersigned individual (hereinafter referred to as the Client/Examinee) who has voluntarily agreed to undergo a psychological evaluation in connection with adoption proceedings, in accordance with applicable laws, rules, and regulations of the Republic of the Philippines.

## I. PURPOSE OF THE PSYCHOLOGICAL EVALUATION

I understand that the purpose of this psychological evaluation is to assess my psychological functioning, emotional stability, personality traits, parenting capacity, interpersonal relationships, and overall readiness to adopt a child. The results of this evaluation are intended to assist the court, adoption agencies, or authorized government bodies in determining my suitability and preparedness for adoption.

I further understand that this evaluation is for assessment and legal purposes, and not primarily for psychological treatment or counseling.

## II. NATURE AND SCOPE OF THE EVALUATION

I have been informed that the psychological evaluation may include, but is not limited to:

Clinical interviews

Psychological tests and assessment instruments

Behavioral observations

Review of relevant records and collateral information, when applicable

I understand that the evaluation may require one or more sessions and that the duration will depend on the assessment requirements.

## III. VOLUNTARY PARTICIPATION

I acknowledge that my participation in this psychological evaluation is voluntary. I understand that I may decline to answer specific questions or withdraw my participation at any time. However, I have been informed that refusal or incomplete participation may affect the completeness of the evaluation and may have implications for the adoption process.

## IV. CONFIDENTIALITY AND LIMITATIONS OF CONFIDENTIALITY

I understand that all information obtained during the psychological evaluation is treated with professional confidentiality. However, I have been informed of the following limitations of confidentiality:

The results of the evaluation will be documented in a psychological report to be submitted to the court, adoption agency, or other authorized institutions involved in the adoption process.

The report may be shared with social workers, legal counsel, or government authorities as required by law or regulation.

The psychologist may be required to provide clarifications, submit testimony, or present findings before the court or relevant authorities.

Confidentiality may be breached if required by law, court order, or when there is a serious risk of harm to the Client/Examinee or others.

I understand that this evaluation does not establish a traditional therapist-client relationship.

## V. RISKS AND DISCOMFORTS

I acknowledge that the evaluation process may involve discussion of personal, family, or emotionally sensitive topics. I understand that this may cause temporary emotional discomfort or distress. I have been informed that I may request clarification, breaks, or support during the evaluation process.

## VI. BENEFITS

I understand that there is no guarantee that this evaluation will result in approval of my adoption application. However, the evaluation may help identify strengths, areas for growth, and recommendations that may support informed decision-making in the adoption process.

## VII. FEES AND PAYMENT

I understand that professional fees for the psychological evaluation, including assessment, report preparation, and possible court appearances, have been explained to me separately. I acknowledge that payment arrangements are my responsibility unless otherwise agreed upon in writing.

## VIII. ACCURACY AND COOPERATION

I acknowledge that the validity of the psychological evaluation depends on my honesty, accuracy, and cooperation throughout the assessment process. I understand that providing false, incomplete, or misleading information may affect the findings and conclusions of the evaluation.

## IX. QUESTIONS AND CLARIFICATIONS

I confirm that I have been given adequate opportunity to ask questions regarding the purpose, procedures, risks, benefits, and limitations of the psychological evaluation, and that all my questions have been answered to my satisfaction.

## X. CONSENT

By signing below, I acknowledge that:

I have read and understood the contents of this Informed Consent Form;

The nature, purpose, and limitations of the psychological evaluation have been clearly explained to me;

I voluntarily agree to undergo the psychological evaluation in relation to adoption proceedings."""

PAP_TITLE = "Adoption Pre-Assessment Questionnaire — Custodian/PAP"
PAP_FIELDS = [
    _sec("I. Background Information"),
    _q("Please tell me about yourself and your relationship with the child."),
    _q("How long has the child been under your care?"),
    _q("Can you describe how the child came into your custody?"),
    _q("What were the circumstances that led to the proposed adoption?"),
    _sec("II. Developmental History"),
    _q("What do you know about the child's pregnancy and birth?"),
    _q("Were there any medical or developmental concerns during infancy or early childhood?"),
    _q("Did the child reach developmental milestones (walking, talking, toilet training) on time?"),
    _q("Has the child experienced any serious illness, hospitalization, or disability?"),
    _sec("III. Family History"),
    _q("What can you tell me about the child's birth parents?"),
    _q("How often did the child have contact with his/her birth parents?"),
    _q("What was the quality of their relationship?"),
    _q("Does the child ask about his/her biological parents?"),
    _q("How does the child react when they are mentioned?"),
    _sec("IV. Emotional and Behavioral Functioning"),
    _q("How would you describe the child's personality?"),
    _q("What are the child's strengths?"),
    _q("What behaviors concern you?"),
    _q("How does the child express happiness, sadness, anger, or fear?"),
    _q("How does the child cope with disappointment or frustration?"),
    _q("Has the child experienced any traumatic events?"),
    _q("How did the child respond to these experiences?"),
    _sec("V. Social Functioning"),
    _q("How does the child interact with family members?"),
    _q("How does the child interact with peers?"),
    _q("Does the child easily make friends?"),
    _q("Does the child have difficulty trusting adults or other children?"),
    _q("How does the child respond to authority figures?"),
    _sec("VI. Academic Functioning"),
    _q("How is the child performing in school?"),
    _q("What are the child's favorite subjects?"),
    _q("Has the child experienced behavioral or learning difficulties in school?"),
    _q("How do teachers describe the child?"),
    _sec("VII. Daily Living Skills"),
    _q("Can the child independently perform age-appropriate self-care activities?"),
    _q("What household responsibilities does the child have?"),
    _q("How does the child spend free time?"),
    _sec("VIII. Relationship with Prospective Adoptive Parent(s)"),
    _q("How did the child first meet the prospective adoptive parent(s)?"),
    _q("Describe their relationship."),
    _q("How does the child behave when around them?"),
    _q("Does the child seek comfort from them?"),
    _q("Have you noticed positive changes since they became involved?"),
    _q("Has the child expressed feelings about the planned adoption?"),
    _sec("IX. Adjustment and Readiness"),
    _q("How do you think the child will adjust to the adoptive family?"),
    _q("What challenges do you anticipate?"),
    _q("What support do you believe the child will need?"),
    _q("Is there anything else you think is important for me to know about the child?"),
]

CHILD_TITLE = "Adoption Pre-Assessment Questionnaire — Child"
CHILD_BODY = "Some questions may not be answered depending on the child's age."
CHILD_FIELDS = [
    _sec("I. Home and Family"),
    _q("Who do you live with?"),
    _q("Tell me about the people at home."),
    _q("Who takes care of you?"),
    _q("What do you like most about living with them?"),
    _q("Is there anything you don't like?"),
    _sec("II. School"),
    _q("What grade are you in?"),
    _q("What do you like about school?"),
    _q("What subjects do you enjoy and least enjoy?"),
    _q("Who are your friends in school?"),
    _sec("III. Feelings"),
    _q("What makes you happy?"),
    _q("What makes you sad?"),
    _q("What makes you angry?"),
    _q("When you are upset, what do you usually do?"),
    _q("Who do you talk to when you have problems?"),
    _sec("IV. Relationships"),
    _q("Who are the people you feel closest to?"),
    _q("Who makes you feel safe?"),
    _q("Who do you enjoy spending time with?"),
    _q("Is there someone you miss?"),
    _sec("V. Biological Parents (if developmentally appropriate)"),
    _q("What do you know about your mother?"),
    _q("What do you know about your father?"),
    _q("Do you remember them?"),
    _q("How do you feel when you think about them?"),
    _q("Do you have any questions about them?"),
    _sec("VI. Prospective Adoptive Parent(s)"),
    _q("Can you tell me about (name of adoptive parent)?"),
    _q("What do you like doing together?"),
    _q("How do they make you feel?"),
    _q("Do you feel safe with them?"),
    _q("If you are sick or scared, would you go to them?"),
    _q("What do you think about living with them?"),
    _sec("VII. Understanding of Adoption (if adoption has already been disclosed)"),
    _q("Has anyone talked to you about adoption?"),
    _q("What do you think adoption means?"),
    _q("How do you feel about being adopted?"),
    _q("Is there anything that worries you?"),
    _q("What are you hoping for in your future family?"),
    _sec("VIII. Self-Concept"),
    _q("Can you tell me three things you like about yourself?"),
    _q("What are you good at?"),
    _q("What do you want to be when you grow up?"),
    _q("If you could wish for three things, what would they be?"),
]

TEMPLATES = [
    (AgencyFormTemplate.CONSENT, CONSENT_TITLE, CONSENT_BODY, []),
    (AgencyFormTemplate.CLINICAL_INTERVIEW, PAP_TITLE, "", PAP_FIELDS),
    (AgencyFormTemplate.CLINICAL_INTERVIEW, CHILD_TITLE, CHILD_BODY, CHILD_FIELDS),
]


class Command(BaseCommand):
    help = "Seed the official agency-authored forms (idempotent; never overwrites edits)."

    def handle(self, *args, **options):
        for form_type, title, body, fields in TEMPLATES:
            obj, created = AgencyFormTemplate.objects.get_or_create(
                form_type=form_type, title=title,
                defaults={
                    "body": body, "fields": fields, "owner": None,
                    "attestation": True, "attested_at": timezone.now(),
                    "active": True,
                })
            self.stdout.write(
                ("Created: " if created else "Exists, skipped: ") + title)
