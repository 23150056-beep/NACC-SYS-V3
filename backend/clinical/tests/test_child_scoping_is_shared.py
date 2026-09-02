"""A psychologist reaches their own assigned children, and nothing else.

This is the rule the whole system rests on. Until now it was written out by
hand at eleven call sites across five modules, and a twelfth endpoint could be
added without it — silently, because a missing filter looks exactly like a
correct one that happens to return everything to an administrator.

The rule now lives once, in `accounts.scoping.scope_to_visible`. This file is
the other half of that: rather than one test per endpoint, written when
somebody remembers, it drives a list. Adding a child-scoped endpoint without
adding it here leaves an obvious gap in an obvious place; adding it here
without scoping the endpoint fails immediately.

Every case is the same shape and it is the shape that matters: the record
belongs to somebody else's child, and the psychologist asking must not see it.
"""
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.models import Role
from children.models import Child
from clinical.models import (
    AgencyFormTemplate, CaseReferral, ClinicalInterviewRecord, ConsentRecord,
    OpinionnaireInvite, PreAssessment, ProblemEntry, PsychologicalReport,
    RemarkNote, ResultEntry, SelfReportFlag, TreatmentPlan,
)

TEMP_MEDIA = tempfile.mkdtemp(prefix="nacc-scoping-test-")
User = get_user_model()


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class PsychologistSeesOnlyAssignedChildrenTest(APITestCase):
    """One record per endpoint, all belonging to a child assigned to someone
    else. Every list must come back empty."""

    def setUp(self):
        Role.objects.create(role_name=Role.ADMINISTRATOR)
        self.psy_role = Role.objects.create(role_name=Role.PSYCHOLOGIST)
        self.mine = User.objects.create_user(
            email="mine@racco1.gov.ph", username="mine", password="pass1234",
            role=self.psy_role)
        self.theirs = User.objects.create_user(
            email="theirs@racco1.gov.ph", username="theirs", password="pass1234",
            role=self.psy_role)
        # The only child in the database belongs to the other psychologist, so
        # any endpoint that forgets to scope returns something and fails.
        self.child = Child.objects.create(
            fullname="Not Mine", case_type="Adoption",
            assigned_psychologist=self.theirs)
        self.template = AgencyFormTemplate.objects.create(
            title="Opinionnaire", form_type=AgencyFormTemplate.SELF_REPORT_GOV)

        upload = lambda: SimpleUploadedFile("f.pdf", b"%PDF-1.4", "application/pdf")
        RemarkNote.objects.create(child=self.child, author=self.theirs, text="x")
        TreatmentPlan.objects.create(child=self.child, author=self.theirs,
                                     objectives="x")
        ProblemEntry.objects.create(child=self.child, logged_by=self.theirs,
                                    description="x")
        ResultEntry.objects.create(child=self.child, entered_by=self.theirs,
                                   summary="x")
        ConsentRecord.objects.create(child=self.child, recorded_by=self.theirs)
        ClinicalInterviewRecord.objects.create(child=self.child,
                                               interviewer=self.theirs)
        PreAssessment.objects.create(child=self.child, psychologist=self.theirs)
        PsychologicalReport.objects.create(child=self.child, author=self.theirs,
                                           file=upload())
        CaseReferral.objects.create(child=self.child, uploaded_by=self.theirs,
                                    file=upload())
        invite = OpinionnaireInvite.objects.create(
            child=self.child, template=self.template,
            expires_at=timezone.now() + timezone.timedelta(days=7))
        SelfReportFlag.objects.create(
            invite=invite, child=self.child, question="q", answer="a",
            source=SelfReportFlag.LEXICON)

        token = self.client.post("/api/auth/login/", {
            "email": "mine@racco1.gov.ph", "password": "pass1234"}).data["access"]
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + token)

    # Every list endpoint that is scoped to the children a user may see. A new
    # one belongs in this tuple.
    SCOPED_LISTS = (
        "/api/children/",
        "/api/remarks/",
        "/api/treatment-plans/",
        "/api/problems/",
        "/api/result-entries/",
        "/api/consents/",
        "/api/interviews/",
        "/api/pre-assessments/",
        "/api/report-files/",
        "/api/case-referrals/",
        "/api/opinionnaire-invites/",
        "/api/self-report-flags/",
    )

    def test_no_scoped_list_leaks_another_psychologists_child(self):
        leaked = []
        for url in self.SCOPED_LISTS:
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 200, f"{url}: {resp.data}")
            if len(resp.data):
                leaked.append(f"{url} returned {len(resp.data)} row(s)")
        self.assertEqual(
            leaked, [],
            "These endpoints returned records belonging to a child assigned to "
            "another psychologist:\n  " + "\n  ".join(leaked) +
            "\nEach one should pass its queryset through "
            "accounts.scoping.scope_to_visible.")

    def test_naming_the_child_directly_does_not_get_round_it(self):
        """The scope is taken from the caller, never from a parameter — asking
        for a specific child by id must not widen it."""
        leaked = []
        for url in self.SCOPED_LISTS:
            if url == "/api/children/":
                continue
            resp = self.client.get(f"{url}?child={self.child.id}")
            self.assertEqual(resp.status_code, 200, f"{url}: {resp.data}")
            if len(resp.data):
                leaked.append(f"{url}?child= returned {len(resp.data)} row(s)")
        self.assertEqual(leaked, [], "\n  ".join(leaked))

    def test_the_child_itself_is_not_retrievable(self):
        resp = self.client.get(f"/api/children/{self.child.id}/")
        self.assertEqual(resp.status_code, 404, resp.data)

    def test_the_same_records_are_visible_to_the_assigned_psychologist(self):
        """The mirror image, so an endpoint cannot pass the tests above by
        returning nothing to anybody."""
        token = self.client.post("/api/auth/login/", {
            "email": "theirs@racco1.gov.ph", "password": "pass1234"}).data["access"]
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + token)
        empty = [url for url in self.SCOPED_LISTS
                 if len(self.client.get(url).data) == 0]
        self.assertEqual(
            empty, [],
            "These returned nothing to the psychologist the child IS assigned "
            "to, so the tests above prove nothing about them: " + str(empty))
